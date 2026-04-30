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

# --- ESTADO GLOBAL SIMULADO (Memória da Fábrica) ---
estado_fabrica = {
    "scada": {
        "temp": 182.0,
        "pressao": 5.0,
        "vazao": 120.0,
        "nivel": 75.0,
        "limite_alarme": 185.0
    },
    "producao": {
        "pecas_boas": 4200,
        "refugo": 45,
        "meta": 6000,
        "inicio_turno": datetime.now()
    }
}

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(20), nullable=False)

def requer_perfil(perfis_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session: return redirect('/') 
            if session.get('role') not in perfis_permitidos: return "Acesso Negado", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- ROTAS DE PÁGINA ---
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

# --- APIs COM LÓGICA REALISTA ---

@app.route('/api/scada_data')
@requer_perfil(['Operador'])
def scada_data():
    # Simulação de Inércia Térmica (Variação de +- 0.4 graus por vez)
    variacao = random.uniform(-0.4, 0.4)
    estado_fabrica["scada"]["temp"] = round(estado_fabrica["scada"]["temp"] + variacao, 1)
    
    # Pressão deriva proporcionalmente à temperatura (Leis da Física)
    estado_fabrica["scada"]["pressao"] = round(5.0 + (estado_fabrica["scada"]["temp"] - 180) * 0.05, 2)
    
    return jsonify({
        "maquina_01": {
            "temp": estado_fabrica["scada"]["temp"],
            "pressao": estado_fabrica["scada"]["pressao"],
            "vazao": round(random.uniform(118, 122), 1),
            "nivel": round(estado_fabrica["scada"]["nivel"] + random.uniform(-0.1, 0.1), 1),
            "alarme": estado_fabrica["scada"]["temp"] > estado_fabrica["scada"]["limite_alarme"]
        },
        "limite": estado_fabrica["scada"]["limite_alarme"]
    })

@app.route('/api/mes_data')
@requer_perfil(['Supervisor'])
def mes_data():
    # Lógica de OEE Real
    disp = 94.2 # % de tempo que a máquina ficou ligada
    perf = round((estado_fabrica["producao"]["pecas_boas"] / 5000) * 100, 1)
    qual = round((1 - (estado_fabrica["producao"]["refugo"] / estado_fabrica["producao"]["pecas_boas"])) * 100, 1)
    oee_global = round((disp/100 * perf/100 * qual/100) * 100, 1)

    return jsonify({
        "kpis": {"oee": oee_global, "disponibilidade": disp, "performance": perf, "qualidade": qual},
        "producao": {"boas": estado_fabrica["producao"]["pecas_boas"], "meta": estado_fabrica["producao"]["meta"], "refugo": estado_fabrica["producao"]["refugo"]},
        "status_maquinas": [
            {"tag": "Torno-01", "status": "Operando", "cor": "success", "eficiencia": "92%"},
            {"tag": "Fresa-02", "status": "Setup", "cor": "warning", "eficiencia": "45%"},
            {"tag": "Robô-03", "status": "Operando", "cor": "success", "eficiencia": "98%"},
            {"tag": "Prensa-04", "status": "Parada Crítica", "cor": "danger", "eficiencia": "0%"}
        ]
    })

@app.route('/api/erp_data')
@requer_perfil(['Engenharia'])
def erp_data():
    # Simulação de custo baseada na produção do MES
    custo_total = estado_fabrica["producao"]["pecas_boas"] * 0.85 # R$ 0,85 por peça
    faturamento = estado_fabrica["producao"]["pecas_boas"] * 2.50 # R$ 2,50 por peça

    return jsonify({
        "financeiro": {
            "receita": f"R$ {faturamento:,.2f}",
            "custo": f"R$ {custo_total:,.2f}",
            "ebitda": f"R$ {(faturamento - custo_total):,.2f}"
        },
        "estoque": [
            {"item": "Aço SAE 1020", "qtd": "14.5 Ton", "acao": "Estoque OK", "cor": "success"},
            {"item": "Fluido de Corte", "qtd": "120 Litros", "acao": "Comprar Agora", "cor": "danger"},
            {"item": "Insertos CNC", "qtd": "45 Unid.", "acao": "Atenção", "cor": "warning"}
        ]
    })

@app.route('/api/setpoint', methods=['POST'])
def setpoint():
    estado_fabrica["scada"]["limite_alarme"] = float(request.get_json().get('valor'))
    return jsonify({"status": "updated"})

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)
