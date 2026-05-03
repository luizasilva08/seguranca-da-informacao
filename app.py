import os
import random
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify, session, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave_super_secreta")
db_url = os.getenv("DATABASE_URL", "sqlite:///banco.db")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# 1. ESTADO GLOBAL DA FÁBRICA (MEMÓRIA)
# ==========================================
limites = {"temp": 185.0, "pressao": 5.0, "vazao": 120.0}

fabrica = {
    # Variáveis SCADA
    "temp": 180.0, "pressao": 4.8, "vazao": 125.0,
    "alarme_ativo": False,
    
    # Variáveis MES
    "pecas": 1200, "oee": 85.0,
    "maq1_status": "Rodando", "maq1_cor": "success",
    
    # Variáveis ERP
    "faturamento": 85000.0, "desperdicio": 340.0
}

# ==========================================
# 2. MOTOR DA FÁBRICA (THREAD DE INTEGRAÇÃO)
# ==========================================
def motor_simulacao():
    """Roda em segundo plano simulando a física da fábrica e a integração"""
    global fabrica, limites
    
    while True:
        # 1. Simula a flutuação natural dos sensores (SCADA)
        fabrica["temp"] += random.uniform(-0.5, 0.6)
        fabrica["pressao"] += random.uniform(-0.05, 0.05)
        fabrica["vazao"] += random.uniform(-1.0, 1.0)

        # Evita que os valores fujam da realidade
        if fabrica["temp"] < 170: fabrica["temp"] = 170
        if fabrica["pressao"] < 4.0: fabrica["pressao"] = 4.0
        
        # 2. Verifica se houve estouro de limite (SCADA afeta o resto)
        fabrica["alarme_ativo"] = fabrica["temp"] > limites["temp"] or fabrica["pressao"] > limites["pressao"]
        
        if fabrica["alarme_ativo"]:
            # EFEITO DOMINÓ SE HOUVER ALARME NO SCADA:
            # MES: Máquina para, OEE cai
            fabrica["maq1_status"] = "Alarme SCADA"
            fabrica["maq1_cor"] = "danger"
            if fabrica["oee"] > 30.0: fabrica["oee"] -= 0.5 
            
            # ERP: Faturamento para, Desperdício dispara
            fabrica["desperdicio"] += 25.5 
            
        else:
            # PRODUÇÃO NORMAL:
            # MES: Produzindo peças, OEE sobe
            fabrica["maq1_status"] = "Rodando"
            fabrica["maq1_cor"] = "success"
            fabrica["pecas"] += 1
            if fabrica["oee"] < 95.0: fabrica["oee"] += 0.1
            
            # ERP: Faturamento subindo, Desperdício estável
            fabrica["faturamento"] += 15.0 
            
        time.sleep(2) # Atualiza a fábrica a cada 2 segundos

# Inicia o motor em segundo plano
thread_fabrica = threading.Thread(target=motor_simulacao, daemon=True)
thread_fabrica.start()


# ==========================================
# 3. BANCO DE DADOS E AUTENTICAÇÃO
# ==========================================
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
    data_hora = db.Column(db.DateTime, default=datetime.now)

def requer_perfil(perfis_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session: return redirect('/') 
            if session.get('role') not in perfis_permitidos:
                registrar_log(f"Tentativa de acesso bloqueado: {request.path}")
                return "Acesso Negado", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def registrar_log(acao):
    usuario = session.get('username', 'Sistema')
    novo_log = AuditLog(acao=acao, usuario=usuario)
    db.session.add(novo_log)
    db.session.commit()

# ==========================================
# 4. ROTAS DO FRONT-END
# ==========================================
@app.route('/')
def pagina_login(): return render_template('login.html')

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
        registrar_log(f"Login realizado ({user.role})")
        destinos = {'Operador': '/scada', 'Supervisor': '/mes', 'Engenharia': '/erp'}
        return jsonify({"mensagem": "Sucesso", "redirect": destinos.get(user.role, '/')})
    return jsonify({"erro": "Credenciais inválidas"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ==========================================
# 5. APIs DE DADOS (AGORA INTEGRADAS!)
# ==========================================
@app.route('/api/monitoramento', methods=['GET'])
@requer_perfil(['Operador'])
def monitoramento():
    global fabrica, limites
    return jsonify({
        "temp": {"valor": fabrica["temp"], "limite": limites["temp"], "alarme": fabrica["temp"] > limites["temp"]},
        "pressao": {"valor": fabrica["pressao"], "limite": limites["pressao"], "alarme": fabrica["pressao"] > limites["pressao"]},
        "vazao": {"valor": fabrica["vazao"], "limite": limites["vazao"], "alarme": fabrica["vazao"] < limites["vazao"]}
    })

@app.route('/api/setpoint', methods=['POST'])
@requer_perfil(['Operador'])
def setpoint():
    global limites
    dados = request.get_json()
    variavel = dados.get('variavel')
    valor = float(dados.get('valor'))
    
    if variavel in limites:
        limites[variavel] = valor
        registrar_log(f"Operador alterou Setpoint {variavel.upper()} para {valor}")
        return jsonify({"mensagem": "Sucesso"})
    return jsonify({"erro": "Variável não encontrada"}), 400

@app.route('/api/mes', methods=['GET'])
@requer_perfil(['Supervisor'])
def dados_mes():
    global fabrica
    
    # Gerando avisos dinâmicos baseados no estado real
    avisos = []
    if fabrica["alarme_ativo"]: avisos.append("ATENÇÃO: Produção interrompida por alarme na Caldeira!")
    else: avisos.append("Produção operando em parâmetros normais.")
        
    return jsonify({
        "oee": fabrica["oee"],
        "pecas_produzidas": fabrica["pecas"],
        "meta": 2000,
        "maquinas": [
            {"nome": "Centro de Usinagem CNC", "status": fabrica["maq1_status"], "cor": fabrica["maq1_cor"]},
            {"nome": "Célula de Solda Robótica", "status": "Rodando", "cor": "success"},
            {"nome": "Esteira de Inspeção Ótica", "status": "Rodando", "cor": "success"}
        ],
        "avisos": avisos
    })

@app.route('/api/erp', methods=['GET'])
@requer_perfil(['Engenharia'])
def dados_erp():
    global fabrica
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(8).all()
    lista_logs = [{"data": l.data_hora.strftime('%H:%M:%S'), "usuario": l.usuario, "acao": l.acao} for l in logs]
    
    # Formata como dinheiro brasileiro
    fat_formatado = f"R$ {fabrica['faturamento']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    desp_formatado = f"R$ {fabrica['desperdicio']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    return jsonify({
        "estoque": [
            {"item": "Aço Inox (Chapa)", "qtd": "4.2 Ton", "status": "OK"},
            {"item": "Parafusos Sextavados", "qtd": "15.000 un", "status": "Baixo"}
        ],
        "kpi_financeiro": {
            "custo_energia": "R$ 1.450,00", 
            "faturamento": fat_formatado, 
            "desperdicio": desp_formatado
        },
        "logs": lista_logs
    })

if __name__ == '__main__':
    with app.app_context(): 
        db.create_all() 
    # use_reloader=False evita que a thread rode duplicada no modo debug do Flask
    app.run(debug=True, use_reloader=False)
