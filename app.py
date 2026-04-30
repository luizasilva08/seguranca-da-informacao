import os
import random
from datetime import datetime
from flask import Flask, request, jsonify, session, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

limite_alarme = 185.0 

# --- MODELOS ---
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

# --- SEGURANÇA E LOGS ---
def requer_perfil(perfis_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect('/') 
            if session.get('role') not in perfis_permitidos:
                registrar_log(f"Tentativa de acesso bloqueada à rota {request.path}")
                return "Acesso Negado: Você não tem permissão para acessar este módulo.", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def registrar_log(acao):
    ip = request.remote_addr
    usuario = session.get('username', 'Anônimo')
    novo_log = AuditLog(acao=acao, usuario=usuario, ip_origem=ip)
    db.session.add(novo_log)
    db.session.commit()

# ==========================================
# ROTAS DE PÁGINAS (FRONTEND)
# ==========================================
@app.route('/')
def pagina_login():
    session.clear() # Garante que volta limpo para a tela inicial
    return render_template('login.html')

@app.route('/scada')
@requer_perfil(['Operador']) # APENAS OPERADOR
def pagina_scada():
    return render_template('scada.html')

@app.route('/mes')
@requer_perfil(['Supervisor']) # APENAS SUPERVISOR
def pagina_mes():
    return render_template('mes.html')

@app.route('/erp')
@requer_perfil(['Engenharia']) # APENAS ENGENHEIRO
def pagina_erp():
    return render_template('erp.html')

# ==========================================
# ROTAS DE DADOS (APIs) E LÓGICA DE LOGIN
# ==========================================
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    
    if user and check_password_hash(user.password_hash, data.get('password')):
        session['username'] = user.username
        session['role'] = user.role
        registrar_log("Login realizado")
        
        # A MÁGICA ACONTECE AQUI: Redirecionamento baseado no cargo
        if user.role == 'Operador':
            destino = '/scada'
        elif user.role == 'Supervisor':
            destino = '/mes'
        elif user.role == 'Engenharia':
            destino = '/erp'
        else:
            destino = '/'

        return jsonify({"mensagem": "Sucesso", "redirect": destino})
    
    return jsonify({"erro": "Credenciais inválidas"}), 401

@app.route('/logout')
def logout():
    registrar_log("Logout realizado")
    session.clear()
    return redirect('/')

@app.route('/api/monitoramento', methods=['GET'])
@requer_perfil(['Operador'])
def monitoramento():
    temp_atual = round(random.uniform(178.0, 188.0), 1)
    return jsonify({"temperatura": temp_atual, "alarme": temp_atual > limite_alarme, "limite": limite_alarme})

@app.route('/api/setpoint', methods=['POST'])
@requer_perfil(['Operador'])
def setpoint():
    global limite_alarme
    limite_alarme = float(request.get_json().get('valor'))
    registrar_log(f"Alteração de Setpoint para {limite_alarme}°C")
    return jsonify({"mensagem": "Sucesso"})

@app.route('/api/mes', methods=['GET'])
@requer_perfil(['Supervisor'])
def dados_mes():
    return jsonify({
        "ordem_servico": "OS-2026-409", "produto": "Válvula Metálica",
        "pecas_produzidas": random.randint(1200, 1250), "meta": 1500,
        "oee": round(random.uniform(82.0, 89.5), 1), "status_linha": "Produção Contínua"
    })

@app.route('/api/erp', methods=['GET'])
@requer_perfil(['Engenharia'])
def dados_erp():
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(8).all()
    lista_logs = [{"data": l.data_hora.strftime('%H:%M:%S'), "usuario": l.usuario, "acao": l.acao} for l in logs]
    
    return jsonify({
        "estoque_materia_prima": "4.2 Toneladas", "custo_energia_diario": "R$ 1.450,00",
        "previsao_faturamento": "R$ 85.000,00", "fornecedor_status": "Aguardando Lote #44",
        "logs": lista_logs
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
    app.run(debug=True)
