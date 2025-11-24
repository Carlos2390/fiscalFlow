import csv
import os
from datetime import datetime, timedelta
from collections import defaultdict
import requests
from bs4 import BeautifulSoup
# Adicionado 'render_template' e removido 'render_template_string' que causava o erro
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import json
from jinja2 import DictLoader

app = Flask(__name__)
app.secret_key = 'segredo_mercearia_familiar'

# Configuração dos Arquivos
DATA_DIR = 'dados_mercearia'
FILES = {
    'produtos': os.path.join(DATA_DIR, 'produtos.csv'),
    'vendas': os.path.join(DATA_DIR, 'vendas.csv'),
    'despesas': os.path.join(DATA_DIR, 'despesas.csv')
}

# Cabeçalhos dos CSVs
HEADERS = {
    'produtos': ['id', 'nome', 'custo', 'preco_venda', 'quantidade', 'fornecedor'],
    'vendas': ['id', 'data', 'produto_id', 'nome_produto', 'quantidade', 'total_venda', 'lucro_estimado'],
    'despesas': ['id', 'data', 'descricao', 'valor', 'categoria']
}

# --- Funções Auxiliares de Banco de Dados (CSV) ---

def init_db():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    for key, filepath in FILES.items():
        if not os.path.exists(filepath):
            with open(filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(HEADERS[key])

def ler_csv(tipo):
    itens = []
    if os.path.exists(FILES[tipo]):
        with open(FILES[tipo], mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                itens.append(row)
    return itens

def escrever_csv(tipo, dados, mode='w'):
    """Se mode='a', adiciona uma linha. Se mode='w', reescreve tudo."""
    filepath = FILES[tipo]
    file_exists = os.path.exists(filepath)
    
    if mode == 'a':
        with open(filepath, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS[tipo])
            if not file_exists:
                writer.writeheader()
            writer.writerow(dados)
    elif mode == 'w':
        with open(filepath, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS[tipo])
            writer.writeheader()
            writer.writerows(dados)

def gerar_id(tipo):
    dados = ler_csv(tipo)
    if not dados:
        return 1
    ids = [int(d['id']) for d in dados]
    return max(ids) + 1

def extrair_itens_nfe(url):
    """Extrai TODOS os itens da NFC-e em uma lista de dicionários.

    Cada item terá: nome, quantidade, custo (valor unitário) e fornecedor.
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    # Tabela de itens: table com id="tabResult"
    tabela = soup.find('table', id='tabResult')
    print(tabela) 
    if not tabela:
        return []

    # Fornecedor: nome da loja no topo (div.txtTopo)
    topo = soup.find('div', class_='txtTopo')
    fornecedor_padrao = topo.get_text(strip=True) if topo else ''

    itens = []
    import re

    for tr in tabela.find_all('tr'):
        # Nome do produto
        span_nome = tr.find('span', class_='txtTit')
        if not span_nome:
            continue
        nome = span_nome.get_text(strip=True)
        if not nome:
            continue

        # Quantidade (ex: "Qtde.:1")
        span_qtd = tr.find('span', class_='Rqtd')
        quantidade = 0
        if span_qtd:
            txt_qtd = span_qtd.get_text(strip=True)
            m = re.search(r"(\d+[\.,]?\d*)", txt_qtd)
            if m:
                try:
                    quantidade = int(float(m.group(1).replace(',', '.')))
                except Exception:
                    quantidade = 0

        # Valor unitário (ex: "Vl. Unit.: 27,95" ou "14,6")
        span_vl_unit = tr.find('span', class_='RvlUnit')
        custo = 0.0
        if span_vl_unit:
            txt_vl = span_vl_unit.get_text(strip=True)
            # pega primeiro número com vírgula decimal (aceita 14,6 ou 14,60)
            m = re.search(r"(\d+[\.\d]*,\d+)", txt_vl)
            if m:
                try:
                    custo = float(m.group(1).replace('.', '').replace(',', '.'))
                except Exception:
                    custo = 0.0

        itens.append({
            'nome': nome,
            'quantidade': quantidade,
            'custo': custo,
            'fornecedor': fornecedor_padrao
        })

    return itens


def extrair_dados_nfe(url):
    """Compat: mantém a assinatura antiga, retornando apenas o primeiro item.

    Essa função ainda é usada no fluxo atual de 1 item. Em breve, vamos
    migrar o código para trabalhar diretamente com a lista retornada por
    extrair_itens_nfe.
    """
    itens = extrair_itens_nfe(url)
    print(itens)
    if not itens:
        return None
    return itens[0]

# --- Templates HTML (Embutidos) ---

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FiscalFlow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-gray-100 font-sans">
    <div class="flex h-screen overflow-hidden">
        <!-- Sidebar -->
        <div class="w-64 bg-slate-800 text-white flex flex-col">
            <div class="p-4 text-center border-b border-slate-700">
                <img src="{{ url_for('static', filename='logo.png') }}" alt="FiscalFlow" class="h-12 mx-auto">
            </div>
            <nav class="flex-1 p-4 space-y-2">
                <a href="{{ url_for('index') }}" class="block p-3 rounded {% if active_page == 'dashboard' %}bg-green-600 hover:bg-green-700 text-white font-bold{% else %}hover:bg-slate-700{% endif %} transition"><i class="fas fa-chart-line mr-2"></i> Dashboard</a>
                <a href="{{ url_for('caixa') }}" class="block p-3 rounded {% if active_page == 'caixa' %}bg-green-600 hover:bg-green-700 text-white font-bold{% else %}hover:bg-slate-700{% endif %} transition"><i class="fas fa-cash-register mr-2"></i> Caixa (Venda)</a>
                <a href="{{ url_for('estoque') }}" class="block p-3 rounded {% if active_page == 'estoque' %}bg-green-600 hover:bg-green-700 text-white font-bold{% else %}hover:bg-slate-700{% endif %} transition"><i class="fas fa-box mr-2"></i> Estoque</a>
                <a href="{{ url_for('despesas') }}" class="block p-3 rounded {% if active_page == 'despesas' %}bg-green-600 hover:bg-green-700 text-white font-bold{% else %}hover:bg-slate-700{% endif %} transition"><i class="fas fa-file-invoice-dollar mr-2"></i> Despesas</a>
                <a href="{{ url_for('relatorios') }}" class="block p-3 rounded {% if active_page == 'relatorios' %}bg-green-600 hover:bg-green-700 text-white font-bold{% else %}hover:bg-slate-700{% endif %} transition"><i class="fas fa-file-csv mr-2"></i> Exportar</a>
            </nav>
            <div class="p-4 border-t border-slate-700 text-xs text-center text-slate-400">
                Sistema de Controle Simples
            </div>
        </div>

        <!-- Main Content -->
        <div class="flex-1 flex flex-col overflow-y-auto">
            <header class="bg-white shadow p-4 flex justify-between items-center">
                <h2 class="text-xl font-semibold text-gray-800">{{ titulo }}</h2>
                <div class="text-sm text-gray-500">{{ data_hoje }}</div>
            </header>
            
            <main class="p-6 flex-1">
                {% with messages = get_flashed_messages(with_categories=true) %}
                  {% if messages %}
                    <div class="mb-4">
                      {% for category, message in messages %}
                        <div class="p-4 rounded-md shadow-md mb-2 
                            {% if category == 'error' %}bg-red-100 text-red-700 border-l-4 border-red-500
                            {% else %}bg-green-100 text-green-700 border-l-4 border-green-500{% endif %}">
                          {{ message }}
                        </div>
                      {% endfor %}
                    </div>
                  {% endif %}
                {% endwith %}

                {% block content %}{% endblock %}
            </main>
        </div>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
{% extends "base" %}
{% block content %}
<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
    <div class="bg-white p-6 rounded-lg shadow-md border-l-4 border-green-500">
        <div class="text-gray-500 text-sm">Vendas</div>
        <div class="text-3xl font-bold text-gray-800">R$ {{ "%.2f"|format(vendas_filtrado) }}</div>
    </div>
    <div class="bg-white p-6 rounded-lg shadow-md border-l-4 border-blue-500">
        <div class="text-gray-500 text-sm">Lucro Estimado</div>
        <div class="text-3xl font-bold text-gray-800">R$ {{ "%.2f"|format(lucro_filtrado) }}</div>
    </div>
    <div class="bg-white p-6 rounded-lg shadow-md border-l-4 border-red-500">
        <div class="text-gray-500 text-sm">Despesas</div>
        <div class="text-3xl font-bold text-gray-800">R$ {{ "%.2f"|format(despesas_filtrado) }}</div>
    </div>
</div>

<div class="bg-white p-4 rounded-lg shadow mb-8">
    <h3 class="text-sm font-semibold text-gray-700 mb-4">Filtros de Análise</h3>
    <form method="get" action="{{ url_for('index') }}" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div>
            <label class="block text-xs font-semibold text-gray-600">Data inicial</label>
            <input type="date" name="data_inicio" value="{{ request.args.get('data_inicio', data_inicio_padrao) }}" class="mt-1 w-full border border-gray-300 rounded-md p-2 text-sm">
        </div>
        <div>
            <label class="block text-xs font-semibold text-gray-600">Data final</label>
            <input type="date" name="data_fim" value="{{ request.args.get('data_fim', data_fim_padrao) }}" class="mt-1 w-full border border-gray-300 rounded-md p-2 text-sm">
        </div>
        <div>
            <label class="block text-xs font-semibold text-gray-600">Produto</label>
            <select name="produto" class="mt-1 w-full border border-gray-300 rounded-md p-2 text-sm">
                <option value="">Todos</option>
                {% for nome in produtos_opcoes %}
                <option value="{{ nome }}" {% if request.args.get('produto') == nome %}selected{% endif %}>{{ nome }}</option>
                {% endfor %}
            </select>
        </div>
        <div>
            <label class="block text-xs font-semibold text-gray-600">Categoria de despesa</label>
            <select name="categoria" class="mt-1 w-full border border-gray-300 rounded-md p-2 text-sm">
                <option value="">Todas</option>
                {% for cat in categorias_opcoes %}
                <option value="{{ cat }}" {% if request.args.get('categoria') == cat %}selected{% endif %}>{{ cat }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="md:col-span-4 flex flex-wrap gap-2 mt-2">
            <button type="submit" class="bg-green-600 text-white px-4 py-2 rounded-md text-sm font-semibold hover:bg-green-700">Aplicar filtros</button>
            <a href="{{ url_for('index') }}" class="px-4 py-2 rounded-md text-sm font-semibold border border-gray-300 text-gray-700 hover:bg-gray-50">Limpar</a>
        </div>
    </form>
</div>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <!-- Evolução de Vendas no Tempo -->
    <div class="bg-white p-6 rounded-lg shadow">
        <h3 class="text-lg font-bold mb-4 text-gray-700">Evolução de Vendas no Tempo</h3>
        <canvas id="evolucaoVendasChart"></canvas>
    </div>
    <!-- Comparativo Mensal: Vendas vs Despesas -->
    <div class="bg-white p-6 rounded-lg shadow">
        <h3 class="text-lg font-bold mb-4 text-gray-700">Comparativo Mensal: Vendas vs Despesas</h3>
        <canvas id="comparativoMensalChart"></canvas>
    </div>
</div>

<div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8 mt-8">
    <div class="bg-white p-4 rounded-lg shadow">
        <h3 class="text-sm font-semibold text-gray-600 mb-2">Vendas por Produto</h3>
        <canvas id="chartVendasProduto" style="width: 100%; height: 420px;"></canvas>
    </div>
    <div class="bg-white p-4 rounded-lg shadow">
        <h3 class="text-sm font-semibold text-gray-600 mb-2">Despesas por Categoria</h3>
        <canvas id="chartDespesasCategoria" style="width: 100%; height: 420px;"></canvas>
    </div>
    <div class="bg-white p-4 rounded-lg shadow">
        <h3 class="text-sm font-semibold text-gray-600 mb-2">Estoque</h3>
        <canvas id="chartEstoque" style="width: 100%; height: 420px;"></canvas>
    </div>
</div>


<h3 class="text-lg font-bold mb-4 text-gray-700">⚠️ Alerta de Estoque Baixo</h3>
<div class="bg-white rounded-lg shadow overflow-hidden mb-8">
    <table class="min-w-full">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Produto</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Qtd Atual</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
            </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
            {% for p in baixo_estoque %}
            <tr>
                <td class="px-6 py-4 whitespace-nowrap">{{ p.nome }}</td>
                <td class="px-6 py-4 whitespace-nowrap font-bold text-red-600">{{ p.quantidade }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-red-500">Repor Urgente</td>
            </tr>
            {% else %}
            <tr>
                <td colspan="3" class="px-6 py-4 text-center text-gray-500">Nenhum produto com estoque crítico.</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<script>
    // Dados para os gráficos antigos (mantidos)
    const despesasCatLabels = {{ despesas_cat_labels|tojson }};
    const despesasCatValores = {{ despesas_cat_valores|tojson }};

    const vendasProdutoLabels = {{ produtos_labels|tojson }};
    const vendasProdutoValores = {{ produtos_vendas_valores|tojson }};

    const estoqueLabels = {{ estoque_labels|tojson }};
    const estoqueValores = {{ estoque_valores|tojson }};

    // Evolução de Vendas no Tempo
    const ctxEvolucao = document.getElementById('evolucaoVendasChart');
    if (ctxEvolucao) {
        new Chart(ctxEvolucao, {
            type: 'line',
            data: {
                labels: {{ evolucao_labels | tojson }},
                datasets: [{
                    label: 'Total de Vendas (R$)',
                    data: {{ evolucao_valores | tojson }},
                    borderColor: 'rgb(34, 197, 94)',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true, ticks: { callback: value => 'R$ ' + value.toFixed(2) } },
                    x: { title: { display: true, text: 'Período' } }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: context => 'R$ ' + context.parsed.y.toFixed(2) } }
                }
            }
        });
    }

    // Comparativo Mensal: Vendas vs Despesas
    const ctxComparativo = document.getElementById('comparativoMensalChart');
    if (ctxComparativo) {
        new Chart(ctxComparativo, {
            type: 'bar',
            data: {
                labels: {{ comparativo_labels | tojson }},
                datasets: [
                    {
                        label: 'Vendas (R$)',
                        data: {{ comparativo_vendas | tojson }},
                        backgroundColor: 'rgba(34, 197, 94, 0.7)',
                        borderColor: 'rgb(34, 197, 94)',
                        borderWidth: 1
                    },
                    {
                        label: 'Despesas (R$)',
                        data: {{ comparativo_despesas | tojson }},
                        backgroundColor: 'rgba(239, 68, 68, 0.7)',
                        borderColor: 'rgb(239, 68, 68)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true, ticks: { callback: value => 'R$ ' + value.toFixed(2) } },
                    x: { title: { display: true, text: 'Mês' } }
                },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: { callbacks: { label: context => context.dataset.label + ': R$ ' + context.parsed.y.toFixed(2) } }
                }
            }
        });
    }

    function buildChartConfigs() {
        const ctxDespesasCategoria = document.getElementById('chartDespesasCategoria');
        if (ctxDespesasCategoria) {
            new Chart(ctxDespesasCategoria, {
                type: 'doughnut',
                data: {
                    labels: despesasCatLabels,
                    datasets: [{
                        data: despesasCatValores,
                        backgroundColor: [
                            'rgba(239,68,68,0.8)',
                            'rgba(249,115,22,0.8)',
                            'rgba(234,179,8,0.8)',
                            'rgba(59,130,246,0.8)',
                            'rgba(16,185,129,0.8)',
                            'rgba(16,185,129,0.8)'
                        ]
                    }]
                },
                options: {
                    responsive: false,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } }
                }
            });
        }

        const ctxVendasProduto = document.getElementById('chartVendasProduto');
        if (ctxVendasProduto) {
            new Chart(ctxVendasProduto, {
                type: 'bar',
                data: {
                    labels: vendasProdutoLabels,
                    datasets: [{
                        label: 'Vendas (R$)',
                        data: vendasProdutoValores,
                        backgroundColor: 'rgba(37,99,235,0.7)'
                    }]
                },
                options: {
                    indexAxis: 'x',
                    responsive: false,
                    maintainAspectRatio: false,
                    scales: {
                        x: { ticks: { autoSkip: true, maxRotation: 45, minRotation: 0 } },
                        y: { beginAtZero: true }
                    }
                }
            });
        }

        const ctxEstoque = document.getElementById('chartEstoque');
        if (ctxEstoque) {
            new Chart(ctxEstoque, {
                type: 'bar',
                data: {
                    labels: estoqueLabels,
                    datasets: [{
                        label: 'Quantidade em Estoque',
                        data: estoqueValores,
                        backgroundColor: 'rgba(34,197,94,0.7)'
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: false,
                    maintainAspectRatio: false,
                    scales: {
                        x: { beginAtZero: true }
                    }
                }
            });
        }

        const ctxRadarProduto = document.getElementById('chartRadarProduto');
        if (ctxRadarProduto) {
            new Chart(ctxRadarProduto, {
                type: 'radar',
                data: {
                    labels: vendasProdutoLabels,
                    datasets: [
                        {
                            label: 'Vendas (R$)',
                            data: vendasProdutoValores,
                            borderColor: 'rgba(59,130,246,1)',
                            backgroundColor: 'rgba(59,130,246,0.2)'
                        },
                        {
                            label: 'Lucro (R$)',
                            data: lucroProdutoValores,
                            borderColor: 'rgba(34,197,94,1)',
                            backgroundColor: 'rgba(34,197,94,0.2)'
                        }
                    ]
                },
                options: {
                    responsive: false,
                    maintainAspectRatio: false,
                    scales: {
                        r: { beginAtZero: true }
                    }
                }
            });
        }
    }

    document.addEventListener('DOMContentLoaded', buildChartConfigs);
</script>
{% endblock %}
"""

ESTOQUE_HTML = """
{% extends "base" %}
{% block content %}
<div class="bg-white p-6 rounded-lg shadow mb-6">
    <h3 class="text-lg font-bold mb-4">Novo Produto / Entrada de Estoque</h3>
    <form action="{{ url_for('adicionar_produto') }}" method="POST" class="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
        <div class="col-span-1 md:col-span-2">
            <label class="block text-sm font-medium text-gray-700">Nome do Produto</label>
            <input type="text" name="nome" value="{{ form_data.nome if form_data else '' }}" class="mt-1 block w-full border border-gray-300 rounded-md p-2">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700">Custo (R$)</label>
            <input type="number" step="0.01" name="custo" value="{{ form_data.custo if form_data else '' }}" class="mt-1 block w-full border border-gray-300 rounded-md p-2">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700">Venda (R$)</label>
            <input type="number" step="0.01" name="preco_venda" value="{{ form_data.preco_venda if form_data else '' }}" class="mt-1 block w-full border border-gray-300 rounded-md p-2">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700">Qtd Inicial</label>
            <input type="number" name="quantidade" value="{{ form_data.quantidade if form_data else '' }}" class="mt-1 block w-full border border-gray-300 rounded-md p-2">
        </div>
        <div class="col-span-1 md:col-span-3">
            <label class="block text-sm font-medium text-gray-700">Fornecedor</label>
            <input type="text" name="fornecedor" value="{{ form_data.fornecedor if form_data else '' }}" class="mt-1 block w-full border border-gray-300 rounded-md p-2">
        </div>
        <div class="col-span-1 md:col-span-2 md:col-span-1">
            <label class="block text-sm font-medium text-gray-700 invisible md:visible">&nbsp;</label>
            <button type="submit" name="acao" value="salvar" class="mt-1 w-full bg-blue-600 text-white p-2 rounded-md hover:bg-blue-700 font-bold">Salvar</button>
        </div>
        <div class="col-span-1 md:col-span-4">
            <label class="block text-sm font-medium text-gray-700">URL da NFC-e (opcional)</label>
            <div class="mt-1 flex gap-2">
                <input type="url" name="url_nfe" placeholder="Cole aqui a URL completa da NFC-e" value="{{ form_data.url_nfe if form_data else '' }}" class="flex-1 border border-gray-300 rounded-md p-2">
                <button type="submit" name="acao" value="preencher_nfe" class="bg-green-600 text-white px-3 py-2 rounded-md text-sm font-semibold hover:bg-green-700 whitespace-nowrap">Pegar dados pela URL</button>
            </div>
        </div>
    </form>
</div>

<div class="bg-white rounded-lg shadow overflow-x-auto">
    <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Produto</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Custo</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Venda</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Qtd</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Fornecedor</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Ações</th>
            </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
            {% for produto in produtos %}
            <tr>
                <td class="px-4 py-2 text-sm text-gray-900">{{ produto.id }}</td>
                <td class="px-4 py-2 text-sm font-medium text-gray-900">{{ produto.nome }}</td>
                <td class="px-4 py-2 text-sm text-gray-900">R$ {{ "%.2f"|format(produto.custo|float) }}</td>
                <td class="px-4 py-2 text-sm text-gray-900">R$ {{ "%.2f"|format(produto.preco_venda|float) }}</td>
                <td class="px-4 py-2 text-sm text-gray-900">{{ produto.quantidade }}</td>
                <td class="px-4 py-2 text-sm text-gray-900">{{ produto.fornecedor }}</td>
                <td class="px-4 py-2 text-sm">
                    <button onclick="openEditModal('{{ produto.id }}', '{{ produto.nome }}', {{ produto.custo }}, {{ produto.preco_venda }}, {{ produto.quantidade }}, '{{ produto.fornecedor }}')" class="px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700">Editar</button>
                    <form method="POST" action="{{ url_for('excluir_produto') }}" class="inline-block ml-1">
                        <input type="hidden" name="id" value="{{ produto.id }}">
                        <button type="submit" class="px-2 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700" onclick="return confirm('Tem certeza que deseja excluir este produto?')">Excluir</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- Modal de edição de produto -->
<div id="editModal" class="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 hidden">
    <div class="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-bold mb-4 text-gray-800">Editar Produto</h3>
        <form method="POST" action="{{ url_for('editar_produto') }}">
            <input type="hidden" name="id" id="edit_id">
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Nome</label>
                    <input type="text" name="nome" id="edit_nome" required class="mt-1 block w-full border border-gray-300 rounded-md p-2">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Custo (R$)</label>
                    <input type="number" step="0.01" name="custo" id="edit_custo" required class="mt-1 block w-full border border-gray-300 rounded-md p-2">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Preço de Venda (R$)</label>
                    <input type="number" step="0.01" name="preco_venda" id="edit_preco_venda" required class="mt-1 block w-full border border-gray-300 rounded-md p-2">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Quantidade</label>
                    <input type="number" name="quantidade" id="edit_quantidade" required class="mt-1 block w-full border border-gray-300 rounded-md p-2">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Fornecedor</label>
                    <input type="text" name="fornecedor" id="edit_fornecedor" class="mt-1 block w-full border border-gray-300 rounded-md p-2">
                </div>
            </div>
            <div class="flex justify-end gap-3 pt-4">
                <button type="button" onclick="closeEditModal()" class="px-4 py-2 rounded-md border border-gray-300 text-gray-700 text-sm hover:bg-gray-50">Cancelar</button>
                <button type="submit" class="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700">Salvar</button>
            </div>
        </form>
    </div>
</div>

<script>
function openEditModal(id, nome, custo, precoVenda, quantidade, fornecedor) {
    document.getElementById('edit_id').value = id;
    document.getElementById('edit_nome').value = nome;
    document.getElementById('edit_custo').value = custo;
    document.getElementById('edit_preco_venda').value = precoVenda;
    document.getElementById('edit_quantidade').value = quantidade;
    document.getElementById('edit_fornecedor').value = fornecedor;
    document.getElementById('editModal').classList.remove('hidden');
}
function closeEditModal() {
    document.getElementById('editModal').classList.add('hidden');
}
</script>
{% if nfe_itens_existentes %}
<!-- Modal de confirmação em lote para itens já cadastrados -->
<div class="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl">
        <h3 class="text-lg font-bold mb-4 text-gray-800">Confirmar adição ao estoque</h3>
        <p class="text-sm text-gray-600 mb-4">Foram encontrados itens desta NFC-e que já estão cadastrados no estoque. Selecione quais deseja atualizar e ajuste as quantidades, se necessário.</p>
        <form method="POST" action="{{ url_for('adicionar_produto') }}" class="space-y-4">
            <input type="hidden" name="acao" value="confirmar_itens_existentes">
            <input type="hidden" name="nfe_json" value='{{ nfe_json }}'>
            <div class="max-h-300 overflow-y-auto border rounded-md">
                <table class="min-w-full text-sm">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Incluir</th>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Produto</th>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Estoque atual</th>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Qtd. na nota</th>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Qtd. a adicionar</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">
                        {% for item in nfe_itens_existentes %}
                        <tr>
                            <td class="px-3 py-2">
                                <input type="checkbox" name="sel_{{ loop.index0 }}" checked class="h-4 w-4 text-green-600 border-gray-300 rounded">
                            </td>
                            <td class="px-3 py-2 font-medium text-gray-800">
                                {{ item.nome }}
                            </td>
                            <td class="px-3 py-2 text-gray-700">{{ item.estoque_atual }}</td>
                            <td class="px-3 py-2 text-gray-700">{{ item.quantidade_nota }}</td>
                            <td class="px-3 py-2">
                                <input type="number" name="qtd_{{ loop.index0 }}" value="{{ item.quantidade_nota }}" min="0" class="w-24 border border-gray-300 rounded-md p-1 text-sm">
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="flex justify-end gap-3 pt-2">
                <a href="{{ url_for('estoque') }}" class="px-4 py-2 rounded-md border border-gray-300 text-gray-700 text-sm hover:bg-gray-50">Cancelar</a>
                <button type="submit" class="px-4 py-2 rounded-md bg-green-600 text-white text-sm font-semibold hover:bg-green-700">Atualizar estoque selecionado</button>
            </div>
        </form>
    </div>
</div>
{% endif %}

{% if nfe_itens_novos %}
<!-- Modal de cadastro em lote para itens novos -->
<div class="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg shadow-xl p-6 w-full max-w-3xl">
        <h3 class="text-lg font-bold mb-4 text-gray-800">Cadastrar novos produtos da NFC-e</h3>
        <p class="text-sm text-gray-600 mb-4">Foram encontrados itens novos nesta NFC-e. Informe o preço de venda para cada um e confirme o cadastro em lote.</p>
        <form method="POST" action="{{ url_for('adicionar_produto') }}" class="space-y-4">
            <input type="hidden" name="acao" value="confirmar_itens_novos">
            <input type="hidden" name="nfe_json_novos" value='{{ nfe_json_novos }}'>
            <div class="max-h-300 overflow-y-auto border rounded-md">
                <table class="min-w-full text-sm">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Nome</th>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Custo (R$)</th>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Qtd.</th>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Fornecedor</th>
                            <th class="px-3 py-2 text-left font-medium text-gray-600">Venda (R$)*</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">
                        {% for item in nfe_itens_novos %}
                        <tr>
                            <td class="px-3 py-2">
                                <input type="text" name="nome_{{ loop.index0 }}" value="{{ item.nome }}" class="w-full border border-gray-300 rounded-md p-1 text-sm">
                            </td>
                            <td class="px-3 py-2">
                                <input type="number" step="0.01" name="custo_{{ loop.index0 }}" value="{{ item.custo }}" readonly class="w-20 border border-gray-300 rounded-md p-1 text-sm bg-gray-50">
                            </td>
                            <td class="px-3 py-2">
                                <input type="number" name="quantidade_{{ loop.index0 }}" value="{{ item.quantidade }}" readonly class="w-16 border border-gray-300 rounded-md p-1 text-sm bg-gray-50">
                            </td>
                            <td class="px-3 py-2">
                                <input type="text" name="fornecedor_{{ loop.index0 }}" value="{{ item.fornecedor }}" readonly class="w-32 border border-gray-300 rounded-md p-1 text-sm bg-gray-50">
                            </td>
                            <td class="px-3 py-2">
                                <input type="number" step="0.01" name="preco_venda_{{ loop.index0 }}" required class="w-24 border border-gray-300 rounded-md p-1 text-sm">
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="flex justify-end gap-3 pt-2">
                <a href="{{ url_for('estoque') }}" class="px-4 py-2 rounded-md border border-gray-300 text-gray-700 text-sm hover:bg-gray-50">Cancelar</a>
                <button type="submit" class="px-4 py-2 rounded-md bg-green-600 text-white text-sm font-semibold hover:bg-green-700">Cadastrar todos</button>
            </div>
        </form>
    </div>
</div>
{% endif %}
{% endblock %}
"""

CAIXA_HTML = """
{% extends "base" %}
{% block content %}
<div class="flex flex-col md:flex-row gap-6">
    <!-- Formulário de Venda -->
    <div class="w-full md:w-1/2">
        <div class="bg-white p-6 rounded-lg shadow-lg border-t-4 border-green-500">
            <h3 class="text-2xl font-bold mb-6 text-gray-800">Registrar Venda</h3>
            <form action="{{ url_for('registrar_venda') }}" method="POST">
                <div class="mb-4">
                    <label class="block text-sm font-bold text-gray-700 mb-2">Selecione o Produto</label>
                    <select name="produto_id" id="produto_select" class="w-full border-2 border-gray-300 rounded-lg p-3 focus:border-green-500 focus:outline-none bg-white" onchange="atualizarPreco()">
                        <option value="" data-preco="0">-- Escolha um produto --</option>
                        {% for p in produtos %}
                            {% if p.quantidade|int > 0 %}
                            <option value="{{ p.id }}" data-preco="{{ p.preco_venda }}">
                                {{ p.nome }} (Estoque: {{ p.quantidade }} | R$ {{ p.preco_venda }})
                            </option>
                            {% endif %}
                        {% endfor %}
                    </select>
                </div>
                
                <div class="mb-4">
                    <label class="block text-sm font-bold text-gray-700 mb-2">Quantidade</label>
                    <input type="number" name="quantidade" id="qtd_input" value="1" min="1" class="w-full border-2 border-gray-300 rounded-lg p-3 text-lg" oninput="calcularTotal()">
                </div>

                <div class="mb-6 p-4 bg-gray-50 rounded-lg text-center">
                    <span class="block text-gray-500 text-sm uppercase">Total da Venda</span>
                    <span class="block text-4xl font-bold text-green-600" id="total_display">R$ 0.00</span>
                </div>

                <button type="submit" class="w-full bg-green-600 text-white p-4 rounded-lg hover:bg-green-700 font-bold text-xl shadow hover:shadow-lg transition transform hover:-translate-y-1">
                    CONFIRMAR VENDA
                </button>
            </form>
        </div>
    </div>

    <!-- Histórico Recente -->
    <div class="w-full md:w-1/2">
        <div class="bg-white p-6 rounded-lg shadow">
            <h3 class="text-lg font-bold mb-4 text-gray-700">Vendas de Hoje</h3>
            <div class="overflow-y-auto max-h-96">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="text-left text-gray-500 border-b">
                            <th class="pb-2">Hora</th>
                            <th class="pb-2">Produto</th>
                            <th class="pb-2">Qtd</th>
                            <th class="pb-2 text-right">Valor</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for v in ultimas_vendas %}
                        <tr class="border-b border-gray-100">
                            <td class="py-3 text-gray-500">{{ v.data.split(' ')[1][:5] }}</td>
                            <td class="py-3 font-medium">{{ v.nome_produto }}</td>
                            <td class="py-3">{{ v.quantidade }}</td>
                            <td class="py-3 text-right font-bold text-green-600">R$ {{ v.total_venda }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
    function atualizarPreco() {
        calcularTotal();
    }

    function calcularTotal() {
        const select = document.getElementById('produto_select');
        const qtd = document.getElementById('qtd_input').value;
        const preco = select.options[select.selectedIndex].getAttribute('data-preco');
        
        if (preco) {
            const total = parseFloat(preco) * parseInt(qtd);
            document.getElementById('total_display').innerText = 'R$ ' + total.toFixed(2);
        } else {
            document.getElementById('total_display').innerText = 'R$ 0.00';
        }
    }
</script>
{% endblock %}
"""

DESPESAS_HTML = """
{% extends "base" %}
{% block content %}
<div class="bg-white p-6 rounded-lg shadow mb-6">
    <h3 class="text-lg font-bold mb-4">Registrar Despesa</h3>
    <form action="{{ url_for('registrar_despesa') }}" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div class="col-span-1 md:col-span-2">
            <label class="block text-sm font-medium text-gray-700">Descrição</label>
            <input type="text" name="descricao" placeholder="Ex: Conta de Luz" required class="mt-1 block w-full border border-gray-300 rounded-md p-2">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700">Valor (R$)</label>
            <input type="number" step="0.01" name="valor" required class="mt-1 block w-full border border-gray-300 rounded-md p-2">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700">Categoria</label>
            <select name="categoria" class="mt-1 block w-full border border-gray-300 rounded-md p-2">
                <option value="Fixa">Fixa (Aluguel, Luz)</option>
                <option value="Variavel">Variável (Manutenção)</option>
                <option value="Pessoal">Retirada Pessoal</option>
            </select>
        </div>
        <div class="col-span-1 md:col-span-4 mt-2">
            <button type="submit" class="bg-red-500 text-white px-6 py-2 rounded-md hover:bg-red-600 font-bold">Lançar Despesa</button>
        </div>
    </form>
</div>

<div class="bg-white rounded-lg shadow">
    <h3 class="p-4 text-lg font-bold border-b">Últimas Despesas</h3>
    <table class="min-w-full">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Data</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Descrição</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Categoria</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Valor</th>
            </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
            {% for d in despesas %}
            <tr>
                <td class="px-6 py-4">{{ d.data }}</td>
                <td class="px-6 py-4 font-medium">{{ d.descricao }}</td>
                <td class="px-6 py-4"><span class="px-2 py-1 text-xs rounded bg-gray-200">{{ d.categoria }}</span></td>
                <td class="px-6 py-4 text-red-600 font-bold">- R$ {{ d.valor }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""

RELATORIOS_HTML = """
{% extends "base" %}
{% block content %}
<div class="bg-white p-6 rounded-lg shadow text-center">
    <h3 class="text-xl font-bold mb-4">Exportar Dados para Excel</h3>
    <p class="text-gray-600 mb-6">Baixe seus dados para analisar detalhadamente.</p>
    
    <div class="flex justify-center gap-4">
        <a href="{{ url_for('download_csv', tipo='vendas') }}" class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">
            <i class="fas fa-download mr-2"></i> Baixar Vendas
        </a>
        <a href="{{ url_for('download_csv', tipo='produtos') }}" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
            <i class="fas fa-download mr-2"></i> Baixar Estoque
        </a>
        <a href="{{ url_for('download_csv', tipo='despesas') }}" class="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700">
            <i class="fas fa-download mr-2"></i> Baixar Despesas
        </a>
    </div>
</div>
{% endblock %}
"""

# --- Configuração do Carregador de Templates (CORREÇÃO DO BUG) ---
TEMPLATES = {
    'base': BASE_TEMPLATE,
    'dashboard': DASHBOARD_HTML,
    'estoque': ESTOQUE_HTML,
    'caixa': CAIXA_HTML,
    'despesas': DESPESAS_HTML,
    'relatorios': RELATORIOS_HTML
}
app.jinja_loader = DictLoader(TEMPLATES)

# --- Rotas do Flask ---

@app.route('/')
def index():
    init_db()
    vendas = ler_csv('vendas')
    despesas = ler_csv('despesas')
    produtos = ler_csv('produtos')
    
    hoje = datetime.now().strftime('%Y-%m-%d')
    mes_atual = datetime.now().strftime('%Y-%m')
    
    # --- Filtros para análise ---
    # Padrão: primeiro e último dia do mês atual
    primeiro_dia = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    ultimo_dia = (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    ultimo_dia = ultimo_dia.strftime('%Y-%m-%d')
    f_data_inicio = request.args.get('data_inicio') or primeiro_dia
    f_data_fim = request.args.get('data_fim') or ultimo_dia
    f_produto = request.args.get('produto') or ''
    f_categoria = request.args.get('categoria') or ''

    # Cálculos principais (sem filtro - visão geral)
    vendas_hoje = sum(float(v['total_venda']) for v in vendas if v['data'].startswith(hoje))
    lucro_mes = sum(float(v['lucro_estimado']) for v in vendas if v['data'].startswith(mes_atual))
    despesas_mes = sum(float(d['valor']) for d in despesas if d['data'].startswith(mes_atual))

    # --- Cálculos com filtro para os cards ---
    produtos_dict = {p['id']: p for p in produtos}
    produtos_dict_nome = {p['nome']: p for p in produtos}
    # Vendas filtradas
    vendas_filtradas = [
        v for v in vendas
        if v['data'] >= f_data_inicio and v['data'] <= f_data_fim
        and (not f_produto or v.get('nome_produto') == f_produto)
        and (not f_categoria or produtos_dict.get(v.get('id_produto'), {}).get('categoria', '') == f_categoria)
    ]
    # Vendas (total filtrado)
    vendas_filtrado = sum(float(v['total_venda']) for v in vendas_filtradas)
    # Lucro Estimado filtrado
    lucro_filtrado = sum(float(v['lucro_estimado']) for v in vendas_filtradas)
    # Despesas filtradas
    despesas_filtradas = [
        d for d in despesas
        if d['data'] >= f_data_inicio and d['data'] <= f_data_fim
        and (not f_categoria or d['categoria'] == f_categoria)
    ]
    despesas_filtrado = sum(float(d['valor']) for d in despesas_filtradas)

    def dentro_periodo(data_str: str) -> bool:
        if not (f_data_inicio or f_data_fim):
            return True
        data_dia = data_str[:10]
        if f_data_inicio and data_dia < f_data_inicio:
            return False
        if f_data_fim and data_dia > f_data_fim:
            return False
        return True

    # Aplicar filtros sobre vendas e despesas usados nos gráficos
    vendas_filtradas = []
    for v in vendas:
        if f_produto and v['nome_produto'] != f_produto:
            continue
        if not dentro_periodo(v['data']):
            continue
        vendas_filtradas.append(v)

    despesas_filtradas = []
    for d in despesas:
        categoria = d.get('categoria', 'Outros') or 'Outros'
        if f_categoria and categoria != f_categoria:
            continue
        if not dentro_periodo(d['data']):
            continue
        despesas_filtradas.append(d)

    # --- Agregações para gráficos (dados filtrados) ---
    # Vendas e lucro por dia
    # Vendas e lucro por produto
    vendas_por_produto = defaultdict(float)
    lucro_por_produto = defaultdict(float)
    for v in vendas_filtradas:
        nome = v['nome_produto']
        vendas_por_produto[nome] += float(v['total_venda'])
        lucro_por_produto[nome] += float(v['lucro_estimado'])

    produtos_labels = list(vendas_por_produto.keys())
    produtos_vendas_valores = [round(vendas_por_produto[n], 2) for n in produtos_labels]
    produtos_lucro_valores = [round(lucro_por_produto[n], 2) for n in produtos_labels]

    # Despesas por categoria e por dia
    despesas_por_categoria = defaultdict(float)
    for d in despesas_filtradas:
        data_dia = d['data'][:10]
        valor = float(d['valor'])
        categoria = d.get('categoria', 'Outros') or 'Outros'
        despesas_por_categoria[categoria] += valor

    despesas_cat_labels = list(despesas_por_categoria.keys())
    despesas_cat_valores = [round(despesas_por_categoria[c], 2) for c in despesas_cat_labels]

    # --- Opções para filtros (todos os produtos e categorias cadastrados) ---
    produtos_opcoes = sorted(set(p['nome'] for p in produtos))
    categorias_opcoes = sorted(set(d.get('categoria', 'Outros') for d in despesas))
    # Evolução de Vendas no Tempo (agrupar por dia/semana/mês conforme filtro)
    evolucao_dict = defaultdict(float)
    for v in vendas_filtradas:
        # Define o nível de agrupamento conforme o intervalo de datas
        delta = datetime.strptime(f_data_fim, '%Y-%m-%d') - datetime.strptime(f_data_inicio, '%Y-%m-%d')
        if delta.days <= 31:
            chave = v['data'][:10]  # dia
        elif delta.days <= 90:
            # semana (YYYY-WW)
            data_obj = datetime.strptime(v['data'][:10], '%Y-%m-%d')
            chave = f"{data_obj.year}-{data_obj.isocalendar()[1]:02d}"
        else:
            chave = v['data'][:7]  # mês
        evolucao_dict[chave] += float(v['total_venda'])
    evolucao_labels = sorted(evolucao_dict.keys())
    evolucao_valores = [round(evolucao_dict[d], 2) for d in evolucao_labels]

    # Comparativo Mensal: Vendas vs Despesas (últimos 12 meses)
    from datetime import date
    hoje = date.today()
    comparativo_labels = []
    comparativo_vendas = []
    comparativo_despesas = []
    for i in range(11, -1, -1):
        mes = (hoje.month - i - 1) % 12 + 1
        ano = hoje.year - (1 if hoje.month - i - 1 < 0 else 0)
        mes_str = f"{ano}-{mes:02d}"
        comparativo_labels.append(datetime(ano, mes, 1).strftime('%b/%Y'))
        total_vendas_mes = sum(float(v['total_venda']) for v in vendas if v['data'].startswith(mes_str))
        total_despesas_mes = sum(float(d['valor']) for d in despesas if d['data'].startswith(mes_str))
        comparativo_vendas.append(round(total_vendas_mes, 2))
        comparativo_despesas.append(round(total_despesas_mes, 2))

    # Estoque por produto
    estoque_labels = [p['nome'] for p in produtos]
    estoque_valores = [int(p['quantidade']) for p in produtos]
    
    # Alerta de estoque (menos de 5 unidades)
    baixo_estoque = [p for p in produtos if int(p['quantidade']) < 5]
    
    # Formatação da data para o header
    data_formatada = datetime.now().strftime('%d/%m/%Y')
    
    # Renderizar via Loader (CORREÇÃO)
    return render_template('dashboard', 
                                titulo="Painel Geral", 
                                data_hoje=data_formatada,
                                vendas_hoje=vendas_hoje,
                                vendas_filtrado=vendas_filtrado,
                                lucro_mes=lucro_mes,
                                despesas_mes=despesas_mes,
                                lucro_filtrado=lucro_filtrado,
                                despesas_filtrado=despesas_filtrado,
                                data_inicio_padrao=primeiro_dia,
                                data_fim_padrao=ultimo_dia,
                                baixo_estoque=baixo_estoque,
                                active_page='dashboard',
                                produtos_labels=produtos_labels,
                                produtos_vendas_valores=produtos_vendas_valores,
                                produtos_lucro_valores=produtos_lucro_valores,
                                despesas_cat_labels=despesas_cat_labels,
                                despesas_cat_valores=despesas_cat_valores,
                                estoque_labels=estoque_labels,
                                estoque_valores=estoque_valores,
                                evolucao_labels=evolucao_labels,
                                evolucao_valores=evolucao_valores,
                                comparativo_labels=comparativo_labels,
                                comparativo_vendas=comparativo_vendas,
                                comparativo_despesas=comparativo_despesas,
                                produtos_opcoes=produtos_opcoes,
                                categorias_opcoes=categorias_opcoes)

@app.route('/estoque')
def estoque():
    produtos = ler_csv('produtos')
    data_formatada = datetime.now().strftime('%d/%m/%Y')
    return render_template('estoque', 
                                titulo="Gerenciar Estoque",
                                data_hoje=data_formatada,
                                produtos=produtos,
                                active_page='estoque',
                                form_data=None,
                                nfe_itens_existentes=None)

@app.route('/adicionar_produto', methods=['POST'])
def adicionar_produto():
    acao = request.form.get('acao')

    # Botão verde: usar dados da NFC-e
    if acao == 'preencher_nfe':
        # Ler campos do formulário apenas quando necessário
        nome = request.form.get('nome', '').strip()
        custo_str = request.form.get('custo', '')
        venda_str = request.form.get('preco_venda', '')
        qtd_str = request.form.get('quantidade', '')
        fornecedor = request.form.get('fornecedor', '')
        url_nfe = request.form.get('url_nfe', '').strip()
        from json import dumps
        itens = extrair_itens_nfe(url_nfe) if url_nfe else []
        if not itens:
            flash('Não foi possível ler os dados da NFC-e. Confira a URL ou preencha manualmente.', 'error')
            produtos = ler_csv('produtos')
            data_formatada = datetime.now().strftime('%d/%m/%Y')
            form_data = {
                'nome': nome,
                'custo': custo_str,
                'preco_venda': venda_str,
                'quantidade': qtd_str,
                'fornecedor': fornecedor,
                'url_nfe': url_nfe
            }
            return render_template('estoque',
                                   titulo="Gerenciar Estoque",
                                   data_hoje=data_formatada,
                                   produtos=produtos,
                                   active_page='estoque',
                                   form_data=form_data,
                                   nfe_itens_existentes=None)

        produtos = ler_csv('produtos')
        itens_existentes = []
        for item in itens:
            nome_item = item['nome'].strip().lower()
            produto = next((p for p in produtos if p['nome'].strip().lower() == nome_item), None)
            if produto:
                try:
                    estoque_atual = int(produto.get('quantidade', 0))
                except ValueError:
                    estoque_atual = 0
                itens_existentes.append({
                    'nome': item['nome'],
                    'quantidade_nota': item['quantidade'],
                    'custo': item['custo'],
                    'fornecedor': item['fornecedor'],
                    'estoque_atual': estoque_atual
                })

        # Determina quais itens são novos
        itens_novos = []
        for item in itens:
            nome_item = item['nome'].strip().lower()
            produto = next((p for p in produtos if p['nome'].strip().lower() == nome_item), None)
            if not produto:
                itens_novos.append(item)

        data_formatada = datetime.now().strftime('%d/%m/%Y')

        # Se não há itens existentes, abrir modal de cadastro em lote para todos os itens, exceto se for só um item (mantém comportamento anterior)
        if not itens_existentes:
            if len(itens) == 1:
                # Comportamento anterior: preencher apenas o primeiro no formulário
                primeiro = itens[0]
                form_data = {
                    'nome': primeiro['nome'],
                    'custo': primeiro['custo'] or custo_str,
                    'preco_venda': venda_str,
                    'quantidade': primeiro['quantidade'] or qtd_str,
                    'fornecedor': primeiro['fornecedor'] or fornecedor,
                    'url_nfe': url_nfe
                }
                flash('Dados preenchidos a partir da NFC-e. Confira e informe o preço de venda.', 'success')
                return render_template('estoque',
                                       titulo="Gerenciar Estoque",
                                       data_hoje=data_formatada,
                                       produtos=produtos,
                                       active_page='estoque',
                                       form_data=form_data,
                                       nfe_itens_existentes=None)
            else:
                # Múltiplos itens novos: abrir modal de cadastro em lote
                data_formatada = datetime.now().strftime('%d/%m/%Y')
                produtos = ler_csv('produtos')
                nfe_json_novos = dumps(itens)
                return render_template('estoque',
                                       titulo="Gerenciar Estoque",
                                       data_hoje=data_formatada,
                                       produtos=produtos,
                                       active_page='estoque',
                                       form_data=None,
                                       nfe_itens_existentes=None,
                                       nfe_itens_novos=itens,
                                       nfe_json_novos=nfe_json_novos)

        # Há itens já cadastrados: abrir modal de confirmação múltipla
        flash('Foram encontrados itens já cadastrados. Confirme a quantidade a adicionar ao estoque.', 'info')
        # Monta payload com existentes e novos para ser lido após a confirmação
        payload = {
            'itens_existentes': itens_existentes,
            'itens_novos': itens_novos
        }
        nfe_json = dumps(payload)
        return render_template('estoque',
                               titulo="Gerenciar Estoque",
                               data_hoje=data_formatada,
                               produtos=produtos,
                               active_page='estoque',
                               form_data=None,
                               nfe_itens_existentes=itens_existentes,
                               nfe_json=nfe_json)

    # Confirmação em lote de itens existentes vindos de NFC-e
    if acao == 'confirmar_itens_existentes':
        produtos = ler_csv('produtos')
        from json import loads, dumps
        try:
            payload = loads(request.form.get('nfe_json', '{}'))
            itens_existentes = payload.get('itens_existentes', [])
            itens_novos = payload.get('itens_novos', [])
        except Exception as e:
            print(f'Erro ao decodificar nfe_json: {e}')
            itens_existentes = []
            itens_novos = []

        print(f'itens_existentes recebidos: {itens_existentes}')
        print(f'Form fields: {list(request.form.keys())}')

        if not itens_existentes:
            flash('Nenhum item para atualizar.', 'error')
            return redirect(url_for('estoque'))

        # Para cada item existente, verificar se foi selecionado e qual quantidade adicionar
        for idx, item in enumerate(itens_existentes):
            sel_key = f'sel_{idx}'
            qtd_key = f'qtd_{idx}'
            print(f'Verificando item {idx}: sel_key={sel_key} in form? {sel_key in request.form}')
            if sel_key not in request.form:
                continue
            nome_item = item['nome']
            qtd_add_str = request.form.get(qtd_key, str(item.get('quantidade_nota', 0)))
            try:
                qtd_add = int(qtd_add_str)
            except ValueError:
                qtd_add = int(item.get('quantidade_nota', 0) or 0)

            print(f'Item {nome_item}: vai adicionar {qtd_add} ao estoque')

            for p in produtos:
                if p['nome'].strip().lower() == nome_item.strip().lower():
                    try:
                        estoque_atual = int(p.get('quantidade', 0))
                    except ValueError:
                        estoque_atual = 0
                    p['quantidade'] = estoque_atual + qtd_add
                    print(f'Estoque de {nome_item}: {estoque_atual} -> {p["quantidade"]}')

        print('Salvando produtos...')
        escrever_csv('produtos', produtos, mode='w')
        flash('Estoque atualizado para os itens selecionados da NFC-e.', 'success')
        # Se houver itens novos, abrir modal de cadastro
        if itens_novos:
            data_formatada = datetime.now().strftime('%d/%m/%Y')
            produtos = ler_csv('produtos')
            nfe_json_novos = dumps(itens_novos)
            return render_template('estoque',
                                   titulo="Gerenciar Estoque",
                                   data_hoje=data_formatada,
                                   produtos=produtos,
                                   active_page='estoque',
                                   form_data=None,
                                   nfe_itens_existentes=None,
                                   nfe_itens_novos=itens_novos,
                                   nfe_json_novos=nfe_json_novos)
        return redirect(url_for('estoque'))

    # Cadastro em lote de itens novos vindos de NFC-e
    if acao == 'confirmar_itens_novos':
        from json import loads
        try:
            itens_novos = loads(request.form.get('nfe_json_novos', '[]'))
        except Exception as e:
            print(f'Erro ao decodificar nfe_json_novos: {e}')
            itens_novos = []

        if not itens_novos:
            flash('Nenhum item novo para cadastrar.', 'error')
            return redirect(url_for('estoque'))

        produtos = ler_csv('produtos')
        for idx, item in enumerate(itens_novos):
            nome = request.form.get(f'nome_{idx}', '').strip()
            custo_str = request.form.get(f'custo_{idx}', '')
            qtd_str = request.form.get(f'quantidade_{idx}', '')
            fornecedor = request.form.get(f'fornecedor_{idx}', '')
            venda_str = request.form.get(f'preco_venda_{idx}', '')

            if not nome or not venda_str:
                flash(f'Item {nome or "(sem nome)"}: nome e preço de venda são obrigatórios.', 'error')
                return redirect(url_for('estoque'))

            try:
                custo = float(custo_str) if custo_str else 0.0
                venda = float(venda_str) if venda_str else 0.0
                qtd = int(qtd_str) if qtd_str else 0
            except ValueError:
                flash(f'Item {nome}: valores inválidos.', 'error')
                return redirect(url_for('estoque'))

            if venda <= custo:
                flash(f'Item {nome}: preço de venda deve ser maior que o custo.', 'error')
                return redirect(url_for('estoque'))

            novo_prod = {
                'id': gerar_id('produtos'),
                'nome': nome,
                'custo': custo,
                'preco_venda': venda,
                'quantidade': qtd,
                'fornecedor': fornecedor
            }
            produtos.append(novo_prod)

        escrever_csv('produtos', produtos, mode='w')
        flash('Novos produtos cadastrados a partir da NFC-e.', 'success')
        return redirect(url_for('estoque'))

    # Botão Salvar: cadastro de novo produto
    if acao == 'salvar':
        # Ler campos do formulário para cadastro/validação
        nome = request.form.get('nome', '').strip()
        custo_str = request.form.get('custo', '')
        venda_str = request.form.get('preco_venda', '')
        qtd_str = request.form.get('quantidade', '')
        fornecedor = request.form.get('fornecedor', '')
        url_nfe = request.form.get('url_nfe', '').strip()
        try:
            custo = float(custo_str) if custo_str else 0.0
        except ValueError:
            custo = 0.0
        try:
            venda = float(venda_str) if venda_str else 0.0
        except ValueError:
            venda = 0.0
        try:
            qtd = int(qtd_str) if qtd_str else 0
        except ValueError:
            qtd = 0

        if venda <= custo:
            flash('Erro: O preço de venda deve ser maior que o custo!', 'error')
            return redirect(url_for('estoque'))

        novo_prod = {
            'id': gerar_id('produtos'),
            'nome': nome,
            'custo': custo,
            'preco_venda': venda,
            'quantidade': qtd,
            'fornecedor': fornecedor
        }
        produtos = ler_csv('produtos')
        produtos.append(novo_prod)
        escrever_csv('produtos', produtos, mode='w')
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('estoque'))

    # Caso padrão: se nenhuma ação conhecida for recebida, volta para Estoque
    return redirect(url_for('estoque'))

@app.route('/editar_produto', methods=['POST'])
def editar_produto():
    prod_id = request.form.get('id')
    nome = request.form.get('nome', '').strip()
    custo_str = request.form.get('custo')
    venda_str = request.form.get('preco_venda')
    qtd_str = request.form.get('quantidade')
    fornecedor = request.form.get('fornecedor', '').strip()
    try:
        custo = float(custo_str) if custo_str else 0.0
    except ValueError:
        custo = 0.0
    try:
        venda = float(venda_str) if venda_str else 0.0
    except ValueError:
        venda = 0.0
    try:
        qtd = int(qtd_str) if qtd_str else 0
    except ValueError:
        qtd = 0

    if venda <= custo:
        flash('Erro: O preço de venda deve ser maior que o custo!', 'error')
        return redirect(url_for('estoque'))

    produtos = ler_csv('produtos')
    for p in produtos:
        if p['id'] == prod_id:
            p['nome'] = nome
            p['custo'] = custo
            p['preco_venda'] = venda
            p['quantidade'] = qtd
            p['fornecedor'] = fornecedor
            break
    escrever_csv('produtos', produtos, mode='w')
    flash('Produto atualizado com sucesso!', 'success')
    return redirect(url_for('estoque'))

@app.route('/excluir_produto', methods=['POST'])
def excluir_produto():
    prod_id = request.form.get('id')
    produtos = ler_csv('produtos')
    produtos = [p for p in produtos if p['id'] != prod_id]
    escrever_csv('produtos', produtos, mode='w')
    flash('Produto excluído com sucesso!', 'success')
    return redirect(url_for('estoque'))

@app.route('/atualizar_estoque', methods=['POST'])
def atualizar_estoque():
    prod_id = request.form['id']
    qtd_add = int(request.form['qtd_add'])
    
    produtos = ler_csv('produtos')
    for p in produtos:
        if p['id'] == prod_id:
            p['quantidade'] = int(p['quantidade']) + qtd_add
            break
            
    escrever_csv('produtos', produtos, mode='w') # Reescreve tudo com a nova qtd
    flash('Estoque atualizado!', 'success')
    return redirect(url_for('estoque'))

@app.route('/caixa')
def caixa():
    produtos = ler_csv('produtos')
    vendas = ler_csv('vendas')
    # Pegar as ultimas 10 vendas invertidas
    ultimas_vendas = sorted(vendas, key=lambda x: x['id'], reverse=True)[:10]
    
    data_formatada = datetime.now().strftime('%d/%m/%Y')
    return render_template('caixa', 
                                titulo="Ponto de Venda",
                                data_hoje=data_formatada,
                                produtos=produtos,
                                ultimas_vendas=ultimas_vendas,
                                active_page='caixa')

@app.route('/registrar_venda', methods=['POST'])
def registrar_venda():
    prod_id = request.form.get('produto_id')
    qtd_venda = int(request.form.get('quantidade'))
    
    if not prod_id:
        flash('Selecione um produto!', 'error')
        return redirect(url_for('caixa'))

    produtos = ler_csv('produtos')
    produto_selecionado = None
    
    # Validar e atualizar estoque
    for p in produtos:
        if p['id'] == prod_id:
            if int(p['quantidade']) < qtd_venda:
                flash(f'Erro: Estoque insuficiente! Disponível: {p["quantidade"]}', 'error')
                return redirect(url_for('caixa'))
            
            p['quantidade'] = int(p['quantidade']) - qtd_venda
            produto_selecionado = p
            break
    
    if produto_selecionado:
        # Gravar atualização de estoque
        escrever_csv('produtos', produtos, mode='w')
        
        # Calcular valores
        total_venda = float(produto_selecionado['preco_venda']) * qtd_venda
        lucro = (float(produto_selecionado['preco_venda']) - float(produto_selecionado['custo'])) * qtd_venda
        
        # Registrar Venda
        nova_venda = {
            'id': gerar_id('vendas'),
            'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'produto_id': prod_id,
            'nome_produto': produto_selecionado['nome'],
            'quantidade': qtd_venda,
            'total_venda': f"{total_venda:.2f}",
            'lucro_estimado': f"{lucro:.2f}"
        }
        escrever_csv('vendas', nova_venda, mode='a')
        flash(f'Venda de R$ {total_venda:.2f} registrada!', 'success')
    
    return redirect(url_for('caixa'))

@app.route('/despesas')
def despesas():
    despesas = ler_csv('despesas')
    # Ordenar por data decrescente
    despesas_sorted = sorted(despesas, key=lambda x: x['data'], reverse=True)
    data_formatada = datetime.now().strftime('%d/%m/%Y')
    return render_template('despesas', 
                                titulo="Controle de Despesas",
                                data_hoje=data_formatada,
                                despesas=despesas_sorted,
                                active_page='despesas')

@app.route('/registrar_despesa', methods=['POST'])
def registrar_despesa():
    nova_despesa = {
        'id': gerar_id('despesas'),
        'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'descricao': request.form['descricao'],
        'valor': f"{float(request.form['valor']):.2f}",
        'categoria': request.form['categoria']
    }
    escrever_csv('despesas', nova_despesa, mode='a')
    flash('Despesa registrada.', 'success')
    return redirect(url_for('despesas'))

@app.route('/relatorios')
def relatorios():
    data_formatada = datetime.now().strftime('%d/%m/%Y')
    return render_template('relatorios', 
                                titulo="Exportação",
                                data_hoje=data_formatada,
                                active_page='relatorios')

@app.route('/download/<tipo>')
def download_csv(tipo):
    filepath = FILES.get(tipo)
    if filepath and os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    flash('Arquivo não encontrado.', 'error')
    return redirect(url_for('relatorios'))

if __name__ == '__main__':
    init_db()
    # Roda o servidor acessível na rede local se quiser acessar pelo celular (mude o host para 0.0.0.0)
    print("Sistema rodando! Acesse http://127.0.0.1:5000 no seu navegador.")
    app.run(debug=True, port=5000)
