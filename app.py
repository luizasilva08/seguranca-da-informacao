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

def requer_perfil(perfis_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session: return redirect('/') 
            if session.get('role') not in perfis_permitidos:
                registrar_log(f"Tentativa de acesso bloqueada à rota {request.path}")
                return "Acesso Negado", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def registrar_log(acao):
    ip = request.remote_addr
    usuario = session.get('username', 'Anônimo')
    novo_log = AuditLog(acao=acao, usuario=usuario, ip_origem=ip)
    db.session.add(novo_log)
    db.session.commit()

# --- ROTAS FRONTEND ---
@app.route('/')
def pagina_login():
    session.clear()
    return render_template('login.html')

@app.route('/scada')
@requer_perfil(['Operador'])
def pagina_scada(): return render_template('scada.html')

@app.route('/mes')
@requer_perfil(['Supervisor'])
def pagina_mes(): return render_template('mes.html')

@app.route('/erp')
@requer_perfil(['Engenharia'])
def pagina_erp(): return render_template('erp.html')

# --- APIS ---
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if user and check_password_hash(user.password_hash, data.get('password')):
        session['username'] = user.username
        session['role'] = user.role
        registrar_log("Login realizado")
        destinos = {'Operador': '/scada', 'Supervisor': '/mes', 'Engenharia': '/erp'}
        return jsonify({"mensagem": "Sucesso", "redirect": destinos.get(user.role, '/')})
    return jsonify({"erro": "Credenciais inválidas"}), 401

@app.route('/logout')
def logout():
    registrar_log("Logout realizado")
    session.clear()
    return redirect('/')

@app.route('/api/monitoramento', methods=['GET'])
@requer_perfil(['Operador'])
def monitoramento():
    temp_atual = round(random.uniform(178.0, 190.0), 1)
    pressao = round(random.uniform(4.5, 5.2), 2)
    vazao = round(random.uniform(115.0, 125.0), 1)
    return jsonify({
        "temperatura": temp_atual, "limite": limite_alarme, "alarme": temp_atual > limite_alarme,
        "pressao": pressao, "vazao": vazao
    })

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
        "ordem_servico": "OS-2026-409", "produto": "Válvula Metálica Hx-2",
        "pecas_produzidas": random.randint(1200, 1250), "meta": 1500,
        "oee": round(random.uniform(82.0, 89.5), 1),
        "maquinas": [
            {"nome": "Fresa CNC 01", "status": "Rodando", "cor": "success"},
            {"nome": "Torno CNC 02", "status": "Em Setup", "cor": "warning"},
            {"nome": "Solda Robótica", "status": "Parada", "cor": "danger"},
            {"nome": "Esteira Insp.", "status": "Rodando", "cor": "success"}
        ],
        "avisos": ["Lote de aço inox chega às 14h", "Manutenção preventiva do Torno 02 agendada", "Meta de produção diária aumentada em 5%"]
    })

@app.route('/api/erp', methods=['GET'])
@requer_perfil(['Engenharia'])
def dados_erp():
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(10).all()
    lista_logs = [{"data": l.data_hora.strftime('%d/%m %H:%M:%S'), "usuario": l.usuario, "acao": l.acao} for l in logs]
    return jsonify({
        "estoque": [
            {"item": "Aço Inox (Chapa)", "qtd": "4.2 Ton", "status": "OK"},
            {"item": "Parafusos Sextavados", "qtd": "15.000 un", "status": "Baixo"},
            {"item": "Óleo Lubrificante", "qtd": "450 L", "status": "OK"}
        ],
        "kpi_financeiro": {"custo_energia": "R$ 1.450,00", "faturamento": "R$ 85.000,00", "desperdicio": "R$ 340,00"},
        "logs": lista_logs
    })

if __name__ == '__main__':
    with app.app_context(): db.create_all() 
    app.run(debug=True)
