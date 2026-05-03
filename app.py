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
app.secret_key = os.getenv("SECRET_KEY", "chave_super_secreta")
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==========================================
# MODELOS DE BANCO DE DADOS
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

# NOVA TABELA: Memória de Estado da Fábrica (Sincroniza SCADA, MES e ERP)
class FabricaState(db.Model):
    __tablename__ = 'fabrica_state'
    id = db.Column(db.Integer, primary_key=True)
    temp = db.Column(db.Float, default=180.0)
    pressao = db.Column(db.Float, default=4.8)
    vazao = db.Column(db.Float, default=125.0)
    limite_temp = db.Column(db.Float, default=185.0)
    limite_pressao = db.Column(db.Float, default=5.0)
    limite_vazao = db.Column(db.Float, default=120.0)
    pecas = db.Column(db.Integer, default=1200)
    oee = db.Column(db.Float, default=85.0)
    faturamento = db.Column(db.Float, default=85000.0)
    desperdicio = db.Column(db.Float, default=340.0)

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
# ROTAS PÁGINAS
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
# MOTOR DE INTEGRAÇÃO EM TEMPO REAL
# ==========================================
@app.route('/api/monitoramento', methods=['GET'])
@requer_perfil(['Operador'])
def monitoramento():
    state = FabricaState.query.first()
    
    # 1. Simula oscilação dos sensores
    state.temp += random.uniform(-0.6, 0.7)
    state.pressao += random.uniform(-0.05, 0.06)
    state.vazao += random.uniform(-0.8, 1.2)
    
    # Travas de física básica
    if state.temp < 170: state.temp = 170.0
    if state.pressao < 4.0: state.pressao = 4.0
    if state.vazao > 135: state.vazao = 135.0

    # 2. Verifica Alarmes INDIVIDUAIS
    al_temp = state.temp > state.limite_temp
    al_pressao = state.pressao > state.limite_pressao
    al_vazao = state.vazao < state.limite_vazao
    alarme_geral = al_temp or al_pressao or al_vazao

    # 3. LÓGICA DE INTEGRAÇÃO (Afeta o resto da fábrica)
    if alarme_geral:
        state.oee = max(30.0, state.oee - 0.3)
        state.desperdicio += 15.0
    else:
        state.pecas += 1
        state.oee = min(95.0, state.oee + 0.05)
        state.faturamento += 10.0

    db.session.commit()

    return jsonify({
        "temp": {"valor": state.temp, "limite": state.limite_temp, "alarme": al_temp},
        "pressao": {"valor": state.pressao, "limite": state.limite_pressao, "alarme": al_pressao},
        "vazao": {"valor": state.vazao, "limite": state.limite_vazao, "alarme": al_vazao}
    })

@app.route('/api/setpoint', methods=['POST'])
@requer_perfil(['Operador'])
def setpoint():
    dados = request.get_json()
    variavel = dados.get('variavel')
    valor = float(dados.get('valor'))
    
    state = FabricaState.query.first()
    if variavel == 'temp': state.limite_temp = valor
    elif variavel == 'pressao': state.limite_pressao = valor
    elif variavel == 'vazao': state.limite_vazao = valor
    
    registrar_log(f"Operador alterou Setpoint {variavel.upper()} para {valor}")
    db.session.commit()
    return jsonify({"mensagem": "Sucesso"})

@app.route('/api/mes', methods=['GET'])
@requer_perfil(['Supervisor'])
def dados_mes():
    state = FabricaState.query.first()
    
    # Se há alarme no banco, a fábrica para
    alarme_geral = state.temp > state.limite_temp or state.pressao > state.limite_pressao or state.vazao < state.limite_vazao
    
    status_maq = "ERRO - PARADA" if alarme_geral else "RODANDO NORMAL"
    cor_maq = "danger" if alarme_geral else "success"
    
    return jsonify({
        "oee": state.oee, "pecas_produzidas": state.pecas, "meta": 2000,
        "alarme_ativo": alarme_geral,
        "maquinas": [
            {"nome": "Fresa CNC 5-Eixos", "status": status_maq, "cor": cor_maq},
            {"nome": "Braço Robótico KUKA", "status": status_maq, "cor": cor_maq},
            {"nome": "Esteira de Inspeção", "status": status_maq, "cor": cor_maq}
        ]
    })

@app.route('/api/erp', methods=['GET'])
@requer_perfil(['Engenharia'])
def dados_erp():
    state = FabricaState.query.first()
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(8).all()
    lista_logs = [{"data": l.data_hora.strftime('%H:%M:%S'), "usuario": l.usuario, "acao": l.acao} for l in logs]
    
    return jsonify({
        "estoque": [
            {"item": "Aço Inox", "qtd": "4.2 Ton", "status": "OK"},
            {"item": "Óleo Lubrificante", "qtd": "250 L", "status": "Baixo se Alarme"}
        ],
        "kpi_financeiro": {
            "custo_energia": "R$ 1.450,00", 
            "faturamento": f"R$ {state.faturamento:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.'), 
            "desperdicio": f"R$ {state.desperdicio:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')
        },
        "logs": lista_logs
    })

if __name__ == '__main__':
    with app.app_context(): 
        db.create_all()
        # Garante que sempre exista 1 linha de estado no banco
        if not FabricaState.query.first():
            db.session.add(FabricaState())
            db.session.commit()
    app.run(debug=True)
