import os
import random
from datetime import datetime
from flask import Flask, request, jsonify, session, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from functools import wraps
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Configuração Segura do Banco de Dados Online
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Variável global para simular o limite de alarme definido pelo usuário
limite_alarme = 185.0 

# --- MODELOS DE BANCO DE DADOS ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(20), nullable=False)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    acao = db.Column(db.String(200), nullable=False)
    usuario = db.Column(db.String(50), nullable=False)
    ip_origem = db.Column(db.String(50))
    data_hora = db.Column(db.DateTime, default=datetime.now)

# --- MIDDLEWARE DE SEGURANÇA (Controle de Acesso / RBAC) ---
def requer_perfil(perfis_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return jsonify({"erro": "Acesso negado. Faça login."}), 401
            if session.get('role') not in perfis_permitidos:
                registrar_log(f"Tentativa de acesso bloqueada à rota {request.path}")
                return jsonify({"erro": "Acesso proibido. Nível insuficiente."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- FUNÇÃO AUXILIAR DE LOG ---
def registrar_log(acao):
    ip = request.remote_addr # Pega o IP de quem acessou
    usuario = session.get('username', 'Anônimo')
    novo_log = AuditLog(acao=acao, usuario=usuario, ip_origem=ip)
    db.session.add(novo_log)
    db.session.commit()

# --- ROTAS DA APLICAÇÃO ---

@app.route('/')
def index():
    # Renderiza a interface visual (index.html)
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    
    # Verifica a senha criptografada
    if user and check_password_hash(user.password_hash, password):
        session['username'] = user.username
        session['role'] = user.role
        
        registrar_log("Login realizado no sistema")
        
        return jsonify({"mensagem": "Sucesso", "role": user.role})
    
    return jsonify({"erro": "Credenciais inválidas"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    registrar_log("Logout realizado")
    session.clear()
    return jsonify({"mensagem": "Logout realizado."})

@app.route('/api/monitoramento', methods=['GET'])
@requer_perfil(['Operador', 'Supervisor', 'Engenharia'])
def monitoramento():
    temp_atual = round(random.uniform(178.0, 188.0), 1)
    
    # Se a temperatura passar do limite configurado, ativa o alarme
    alarme_ativo = temp_atual > limite_alarme
    
    return jsonify({
        "temperatura": temp_atual, 
        "alarme": alarme_ativo,
        "limite": limite_alarme
    })

@app.route('/api/setpoint', methods=['POST'])
@requer_perfil(['Supervisor', 'Engenharia'])
def setpoint():
    global limite_alarme
    data = request.get_json()
    novo_valor = float(data.get('valor'))
    limite_alarme = novo_valor
    
    registrar_log(f"Alteração de Setpoint de Alarme para {novo_valor}°C")
    return jsonify({"mensagem": f"Alarme configurado para {novo_valor}°C"})

@app.route('/api/auditoria', methods=['GET'])
@requer_perfil(['Engenharia'])
def auditoria():
    # Busca os últimos 15 logs do banco
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(15).all()
    lista_logs = [{
        "id": l.id, 
        "acao": l.acao, 
        "usuario": l.usuario, 
        "ip": l.ip_origem, 
        "data": l.data_hora.strftime('%d/%m %H:%M:%S')
    } for l in logs]
    return jsonify(lista_logs)

if __name__ == '__main__':
    with app.app_context():
        # Cria as tabelas no Supabase caso não existam
        db.create_all() 
    app.run(debug=True)