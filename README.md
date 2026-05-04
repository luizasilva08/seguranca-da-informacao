# 🛡️ Nexus UI: Indústria 4.0 & Cibersegurança

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-lightgrey.svg)
![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E.svg)
![Render](https://img.shields.io/badge/Render-Deploy-black.svg)

Este repositório contém o projeto da Unidade Curricular de **Programação Para Coleta de Dados em Automação**, consistindo num sistema de login (Operador, Supervisor e Engenharia) com foco em Segurança da Informação.

O sistema demonstra como vulnerabilidades comuns na indústria podem ser reduzidas através de boas práticas de programação, controle de acessos e monitorização em tempo real.

Este projeto foi desenvolvido por alunos do CentroWEG (Turma MA - 78).

## 👥 Equipe
* Ana Clara Rodrigues Abreu;
* Emanuel Coelho Lehnert;
* Luíza da Silva;
---

## 🛠️ Tecnologias e Ferramentas Utilizadas

Este projeto foi desenvolvido com foco em praticidade para apresentação acadêmica, utilizando as seguintes ferramentas:

* **IDE / Desenvolvimento Local:** Visual Studio Code (VS Code).
* **Back-end:** Python, Flask, SQLAlchemy (ORM).
* **Front-end:** HTML5, CSS3 (Bootstrap 5.3), JavaScript puro.
* **Banco de Dados:** **Supabase** (PostgreSQL em nuvem).
* **Hospedagem / Deploy:** **Render** (com integração contínua diretamente deste repositório GitHub para gerar uma URL única e acessível).

> ⚠️ **Nota de Arquitetura (Segurança vs. Acessibilidade):** > Em um ambiente industrial real (ICS/SCADA), a utilização de um banco de dados em nuvem (como o Supabase) não é recomendada devido aos rigorosos requisitos de segurança, latência e necessidade de isolamento de rede (*Air-Gap*). No entanto, para fins acadêmicos e para garantir a viabilidade da apresentação do projeto em qualquer computador, optou-se por essa abordagem em nuvem.

---

## 🎯 Funcionalidades e Módulos

O projeto está dividido em quatro interfaces principais, protegidas por autenticação e níveis de acesso (RBAC):

1. **🔐 Login Seguro:** Proteção contra Força Bruta (bloqueio de IP por tentativas falhas) e senhas com hash criptográfico.
2. **🏭 SCADA (Operador):** Monitoramento em tempo real de Temperatura, Pressão e Vazão com alarmes dinâmicos.
3. **🗺️ MES (Supervisor):** Visualização do estado das máquinas.
4. **📊 ERP & Compliance (Engenharia):** Dashboard executivo com exportação de relatórios (PDF/CSV), auditoria contínua de logs e verificação de assinatura digital de lotes de produção.

---

## 🚀 Como Acessar o Projeto

### Opção 1: Acesso Online (Recomendado)
O projeto está hospedado no Render. Você pode testar o sistema completo através do link:
👉 **[https://seguranca-da-informacao.onrender.com/]**

### Opção 2: Clone este repositório

```bash
git clone [https://github.com/luizasilva08/seguranca-da-informacao.git](https://github.com/luizasilva08/seguranca-da-informacao.git)
cd seguranca-da-informacao
