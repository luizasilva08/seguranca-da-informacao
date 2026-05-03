import os
import random
import json
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave_super_secreta")
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==========================================
# MODELOS DE BASE DE DADOS
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

class FailedLogin(db.Model):
    __tablename__ = 'failed_logins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    ip_address = db.Column(db.String(50))
    attempt_time = db.Column(db.DateTime, default=datetime.now)

class FabricaState(db.Model):
    __tablename__ = 'fabrica_state'
    id = db.Column(db.Integer, primary_key=True)
    temp = db.Column(db.Float, default=180.0)
    pressao = db.Column(db.Float, default=4.8)
    vazao = db.Column(db.Float, default=125.0)
    limite_temp = db.Column(db.Float, default=185.0)
    limite_pressao = db.Column(db.Float, default=5.0)
    limite_vazao = db.Column(db.Float, default=120.0)
    pecas = db.Column(db.Integer, default=0)
    oee = db.Column(db.Float, default=85.0)
    faturamento = db.Column(db.Float, default=0.0)
    desperdicio = db.Column(db.Float, default=0.0)
    ultima_atualizacao = db.Column(db.DateTime, default=datetime.now)
    saude_maquina = db.Column(db.Float, default=100.0)
    taxa_defeitos = db.Column(db.Float, default=2.4)
    tempo_ciclo = db.Column(db.Float, default=45.0)
    lote_atual = db.Column(db.String(50), default='L-2024-88')

def get_estado_fabrica():
    state = FabricaState.query.first()
    if not state:
        state = FabricaState()
        db.session.add(state)
        db.session.commit()
    return state

def requer_perfil(perfis_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session: return redirect('/') 
            if session.get('role') not in perfis_permitidos: return "Acesso Negado", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def registrar_log(acao):
    usuario = session.get('username', 'Sistema')
    db.session.add(AuditLog(acao=acao, usuario=usuario))
    db.session.commit()

# ==========================================
# ROTAS DE PÁGINAS E LOGIN (ANTI-BRUTE FORCE)
# ==========================================
@app.route('/')
def pagina_login(): return render_template('login.html')

@app.route('/scada')
@requer_perfil(['Operador'])
def pagina_scada(): return render_template('scada.html', usuario=session.get('username'))

@app.route('/mes')
@requer_perfil(['Supervisor'])
def pagina_mes(): return render_template('mes.html')

@app.route('/erp')
@requer_perfil(['Engenharia'])
def pagina_erp(): return render_template('erp.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    ip_address = request.remote_addr or "127.0.0.1"
    
    # PROTEÇÃO: Bloqueio por Brute Force (Mais de 3 erros em 5 minutos)
    limite_tempo = datetime.now() - timedelta(minutes=5)
    tentativas = FailedLogin.query.filter(FailedLogin.ip_address == ip_address, FailedLogin.attempt_time >= limite_tempo).count()
    
    if tentativas >= 3:
        registrar_log(f"INCIDENTE DE SEGURANÇA: Bloqueio de IP {ip_address}")
        return jsonify({"erro": "IP bloqueado por múltiplas falhas. Tente em 5 min.", "bloqueado": True}), 403

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, data.get('password')):
        session['username'] = user.username
        session['role'] = user.role
        registrar_log(f"Login efetuado com sucesso ({user.role})")
        FailedLogin.query.filter_by(ip_address=ip_address).delete()
        db.session.commit()
        destinos = {'Operador': '/scada', 'Supervisor': '/mes', 'Engenharia': '/erp'}
        return jsonify({"mensagem": "Sucesso", "redirect": destinos.get(user.role, '/')})
    
    db.session.add(FailedLogin(username=username, ip_address=ip_address))
    db.session.commit()
    return jsonify({"erro": "Credenciais inválidas"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ==========================================
# MOTOR DA FÁBRICA
# ==========================================
def rodar_motor_fabrica(state):
    agora = datetime.now()
    if state.ultima_atualizacao and (agora - state.ultima_atualizacao).total_seconds() < 2.0:
        return state

    # Simulação normal (oscilação)
    state.temp += random.uniform(-0.6, 0.7)
    state.pressao += random.uniform(-0.05, 0.06)
    state.vazao += random.uniform(-0.8, 1.2)
    
    if state.temp < 170: state.temp = 170.0
    if state.pressao < 4.0: state.pressao = 4.0
    if state.vazao > 135: state.vazao = 135.0

    state.saude_maquina = max(0.0, state.saude_maquina - 0.05)
    
    # Simulação de variação de Qualidade
    state.taxa_defeitos += random.uniform(-0.1, 0.1)
    if state.taxa_defeitos < 0.5: state.taxa_defeitos = 0.5
    if state.taxa_defeitos > 8.0: state.taxa_defeitos = 8.0

    state.tempo_ciclo += random.uniform(-0.5, 0.5)
    if state.tempo_ciclo < 35.0: state.tempo_ciclo = 35.0

    al_geral = (state.temp > state.limite_temp) or (state.pressao > state.limite_pressao) or (state.vazao < state.limite_vazao)
    if al_geral:
        state.oee = max(30.0, state.oee - 0.3)
        state.desperdicio += 15.0
    else:
        state.pecas += 1
        state.oee = min(95.0, state.oee + 0.05)
        state.faturamento += 10.0

    state.ultima_atualizacao = agora
    db.session.commit()
    return state

# ==========================================
# API DE DADOS E SEGURANÇA
# ==========================================
@app.route('/api/monitoramento', methods=['GET'])
@requer_perfil(['Operador'])
def monitoramento():
    state = rodar_motor_fabrica(get_estado_fabrica())
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(6).all()
    lista_logs = [{"hora": l.data_hora.strftime('%H:%M:%S'), "acao": l.acao} for l in logs]
    
    payload = {
        "temp": {"valor": state.temp, "limite": state.limite_temp, "alarme": state.temp > state.limite_temp},
        "pressao": {"valor": state.pressao, "limite": state.limite_pressao, "alarme": state.pressao > state.limite_pressao},
        "vazao": {"valor": state.vazao, "limite": state.limite_vazao, "alarme": state.vazao < state.limite_vazao},
        "logs": lista_logs
    }
    
    # ASSINATURA ANTI-MITM
    CHAVE_SECRETA = "INDUSTRIAS_KEY_2024"
    payload_json = json.dumps(payload)
    assinatura = hashlib.sha256((payload_json + CHAVE_SECRETA).encode('utf-8')).hexdigest()
    
    return jsonify({"payload": payload_json, "assinatura": assinatura})

@app.route('/api/mes', methods=['GET'])
@requer_perfil(['Supervisor'])
def dados_mes():
    state = rodar_motor_fabrica(get_estado_fabrica())
    alarme_geral = state.temp > state.limite_temp or state.pressao > state.limite_pressao or state.vazao < state.limite_vazao
    
    return jsonify({
        "oee": state.oee, "pecas_produzidas": state.pecas, "meta": 2000,
        "alarme_ativo": alarme_geral,
        "saude_maquina": state.saude_maquina,
        "taxa_defeitos": state.taxa_defeitos,
        "tempo_ciclo": state.tempo_ciclo,
        "maquinas": [
            {"nome": "Fresa CNC 5-Eixos", "status": "ERRO" if alarme_geral else "RODANDO", "cor": "danger" if alarme_geral else "success"},
            {"nome": "Robô de Solda", "status": "ERRO" if alarme_geral else "RODANDO", "cor": "danger" if alarme_geral else "success"},
            {"nome": "Esteira Inspeção", "status": "ERRO" if alarme_geral else "RODANDO", "cor": "danger" if alarme_geral else "success"}
        ]
    })

@app.route('/api/erp', methods=['GET'])
@requer_perfil(['Engenharia'])
def dados_erp():
    state = rodar_motor_fabrica(get_estado_fabrica())
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(8).all()
    
    # CÁLCULO DA POSTURA DE SEGURANÇA
    score = 100
    if state.saude_maquina < 40: score -= 20
    falhas_login = FailedLogin.query.filter(FailedLogin.attempt_time >= (datetime.now() - timedelta(minutes=60))).count()
    score -= (falhas_login * 5)
    score = max(0, score)

    return jsonify({
        "seguranca_score": score,
        "falhas_login": falhas_login,
        "lote_atual": state.lote_atual,
        "data_lote": state.ultima_atualizacao.strftime('%d/%m/%Y'),
        "kpi_financeiro": {
            "custo_energia": "R$ 1.450,00",
            "faturamento": f"R$ {state.faturamento:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.'), 
            "desperdicio": f"R$ {state.desperdicio:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')
        },
        "logs": [{"data": l.data_hora.strftime('%H:%M:%S'), "usuario": l.usuario, "acao": l.acao} for l in logs]
    })

@app.route('/api/setpoint', methods=['POST'])
@requer_perfil(['Operador'])
def setpoint():
    d = request.get_json()
    state = get_estado_fabrica()
    v, valor = d.get('variavel'), float(d.get('valor'))
    if v == 'temp': state.limite_temp = valor
    elif v == 'pressao': state.limite_pressao = valor
    elif v == 'vazao': state.limite_vazao = valor
    registrar_log(f"Setpoint alterado: {v.upper()} = {valor}")
    db.session.commit()
    return jsonify({"mensagem": "Sucesso"})

@app.route('/api/verificar_lote', methods=['POST'])
def verificar_lote():
    state = get_estado_fabrica()
    lote = state.lote_atual
    assinatura = hashlib.sha256((lote + "CHAVE_PRODUCAO").encode()).hexdigest()
    registrar_log(f"Assinatura do lote {lote} verificada digitalmente.")
    return jsonify({"status": "VÁLIDA", "assinatura": assinatura[:16].upper()})

@app.route('/api/manutencao', methods=['POST'])
def reset_manutencao():
    state = get_estado_fabrica()
    state.saude_maquina = 100.0
    registrar_log("Manutenção Preventiva Registada")
    db.session.commit()
    return jsonify({"status": "ok"})

with app.app_context(): 
    db.create_all()
    get_estado_fabrica()

if __name__ == '__main__':
    app.run(debug=True)
