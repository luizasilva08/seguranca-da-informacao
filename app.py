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

# Estado Global Simulado
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
            if session.get('role') not in perfis_permitidos: return "Acesso Negado", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

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

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if user and check_password_hash(user.password_hash, data.get('password')):
        session['username'] = user.username
        session['role'] = user.role
        destinos = {'Operador': '/scada', 'Supervisor': '/mes', 'Engenharia': '/erp'}
        return jsonify({"mensagem": "Sucesso", "redirect": destinos.get(user.role, '/')})
    return jsonify({"erro": "Incorreto"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- APIs DE DADOS REALISTAS ---

@app.route('/api/scada_data')
@requer_perfil(['Operador'])
def scada_data():
    return jsonify({
        "maquina_01": {
            "temp": round(random.uniform(175, 190), 1),
            "pressao": round(random.uniform(4.8, 5.5), 2),
            "vazao": round(random.uniform(110, 130), 1),
            "nivel": round(random.uniform(70, 85), 1),
            "status": "OPERANDO",
            "alarme": True if limite_alarme < 185 else False # Simulação lógica
        },
        "limite_config": limite_alarme
    })

@app.route('/api/mes_data')
@requer_perfil(['Supervisor'])
def mes_data():
    return jsonify({
        "oee": {"global": 87.5, "disponibilidade": 92, "performance": 95, "qualidade": 99},
        "producao": {"atual": random.randint(4500, 5000), "meta": 6000, "refugo": 12},
        "maquinas": [
            {"id": "CNC-01", "status": "Ativa", "load": 85, "temp": 45},
            {"id": "ROB-02", "status": "Manutenção", "load": 0, "temp": 22},
            {"id": "EST-03", "status": "Ativa", "load": 40, "temp": 38},
            {"id": "INV-04", "status": "Alerta", "load": 98, "temp": 72}
        ],
        "alertas": ["Troca de ferramenta CNC-01 em 2h", "Nível baixo de fluido hidráulico EST-03"]
    })

@app.route('/api/erp_data')
@requer_perfil(['Engenharia'])
def erp_data():
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(6).all()
    return jsonify({
        "financeiro": {"receita": "R$ 452.000", "custo": "R$ 128.000", "margem": "72%"},
        "estoque": [
            {"item": "Polímero PP", "qtd": "1.200kg", "critico": False},
            {"item": "Pigmento Azul", "qtd": "50kg", "critico": True},
            {"item": "Embalagens G", "qtd": "5.000un", "critico": False}
        ],
        "logs": [{"u": l.usuario, "a": l.acao, "d": l.data_hora.strftime('%H:%M')} for l in logs]
    })

@app.route('/api/setpoint', methods=['POST'])
def setpoint():
    global limite_alarme
    limite_alarme = float(request.get_json().get('valor'))
    return jsonify({"s": "ok"})

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)
