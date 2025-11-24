<img width="325" height="75" alt="logo" src="https://github.com/user-attachments/assets/f507bc93-e37b-4ac5-904a-410bfba7bc60" />

Sistema web para gestão de vendas, estoque e despesas de pequenos estabelecimentos comerciais.

## 📋 Funcionalidades

### Dashboard
- **Cards principais**: Vendas, Lucro Estimado e Despesas com filtros de data
- **Gráficos interativos**:
  - Evolução de Vendas no Tempo (linha)
  - Comparativo Mensal: Vendas vs Despesas (barra agrupada)
  - Vendas por Produto (barra)
  - Despesas por Categoria (pizza)
  - Estoque Baixo (barra com alertas)
- **Filtros dinâmicos**: por período, produto e categoria de despesa
- **Data padrão**: primeiro e último dia do mês atual

### Gestão de Estoque
- Cadastro de produtos com: nome, custo, preço de venda, quantidade, fornecedor
- **Importação via NFC-e**: extração automática de itens de notas fiscais eletrônicas
- **Modais de confirmação**: para itens já existentes e novos itens
- **Edição e exclusão** de produtos via modal
- **Alerta automático** de produtos com estoque baixo (< 5 unidades)

### Caixa (Vendas)
- Registro rápido de vendas
- Seleção de produtos com preço automático
- Cálculo automático do total
- Histórico de vendas com data e hora

### Despesas
- Registro de despesas com categorias
- Categorias pré-definidas: Fixa, Variável, Pessoal
- Data de registro automática

### Relatórios
- Exportação de dados em CSV
- Relatórios de vendas, produtos e despesas

## 🚀 Instalação e Execução

### Pré-requisitos
- Python 3.8 ou superior
- Git (opcional)

### Passo 1 - Clonar o projeto
```bash
git clone https://github.com/Carlos2390/fiscalFlow.git
cd fiscalFlow
```

### Passo 2 - Criar ambiente virtual
```bash
python -m venv env

# Windows
env\Scripts\activate

# Linux/Mac
source env/bin/activate
```

### Passo 3 - Instalar dependências
```bash
pip install flask requests beautifulsoup4
```

### Passo 4 - Estrutura de pastas
O projeto já vem com a estrutura necessária:
```
teste/
├── dados_mercearia/
│   ├── produtos.csv
│   ├── vendas.csv
│   └── despesas.csv
├── static/
│   └── logo.png
└── main.py
```

### Passo 5 - Executar o aplicativo
```bash
python main.py
```

O sistema estará disponível em: http://127.0.0.1:5000

## 📖 Como Usar

### 1. Configuração Inicial

#### Adicionar Logo
- Coloque seu arquivo de logo em `static/logo.png`
- A logo aparecerá automaticamente na barra lateral

#### Cadastrar Produtos
1. Acesse **Estoque** no menu lateral
2. Use o formulário para adicionar produtos manualmente OU
3. Importe via NFC-e (veja abaixo)

### 2. Importação via NFC-e

O sistema extrai automaticamente itens de NFC-e da SEFAZ-SP:

1. **Copie o link da NFC-e**:
   - Acesse: https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/
   - Cole a chave de acesso e consulte
   - Copie a URL completa da página de resultados

2. **Importe no sistema**:
   - Em **Estoque**, clique "Adicionar Produto"
   - Cole a URL da NFC-e no campo correspondente
   - O sistema extrairá todos os itens automaticamente

3. **Confirme os itens**:
   - **Itens já cadastrados**: aparecerão para você confirmar e atualizar quantidades
   - **Itens novos**: aparecerão em lote para cadastro rápido

### 3. Registrar Vendas

1. Acesse **Caixa (Venda)** no menu
2. Selecione o produto no dropdown
3. Digite a quantidade vendida
4. O total é calculado automaticamente
5. Clique "Registrar Venda"

### 4. Registrar Despesas

1. Acesse **Despesas** no menu
2. Preencha:
   - Descrição (ex: "Conta de Luz")
   - Valor
   - Categoria (Fixa/Variável/Pessoal)
3. Clique "Registrar Despesa"

### 5. Usar o Dashboard

1. **Visualização padrão**: mostra dados do mês atual
2. **Filtrar por período**:
   - Altere as datas de início e fim
   - Clique "Aplicar filtros"
3. **Filtrar por produto**: selecione um produto específico
4. **Filtrar por categoria**: selecione categoria de despesa
5. **Limpar filtros**: clique no botão "Limpar"

### 6. Gerenciar Produtos

#### Editar Produto
1. Em **Estoque**, clique o ícone de edição (✏️)
2. Altere os dados no modal
3. Clique "Salvar"

#### Excluir Produto
1. Em **Estoque**, clique o ícone de lixeira (🗑️)
2. Confirme a exclusão no modal

#### Ver Estoque Baixo
- No Dashboard, produtos com < 5 unidades aparecem em vermelho
- Gráfico "Estoque" mostra visualmente os níveis atuais

### 7. Exportar Relatórios

1. Acesse **Exportar** no menu
2. Escolha o tipo de relatório:
   - Relatório de Vendas
   - Relatório de Produtos
   - Relatório de Despesas
3. O arquivo CSV será baixado automaticamente

## 📝 Desenvolvimento

### Tecnologias
- **Backend**: Flask (Python)
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **Gráficos**: Chart.js
- **Ícones**: Font Awesome
- **Parsing**: BeautifulSoup (para NFC-e)

