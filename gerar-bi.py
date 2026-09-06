import argparse
import csv
import json
import os
import html as html_lib


def ler_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def calcular_kpis(linhas_flat):
    total_registros = len(linhas_flat)
    valores = [float(r["vlr_transacao_movimento"]) for r in linhas_flat if r.get("vlr_transacao_movimento")]
    valor_total = sum(valores)
    ticket_medio = valor_total / total_registros if total_registros else 0
    associados_distintos = len({r["id_associado"] for r in linhas_flat})
    cartoes_distintos = len({r["numero_cartao"] for r in linhas_flat})
    return {
        "total_registros": total_registros,
        "valor_total": valor_total,
        "ticket_medio": ticket_medio,
        "associados_distintos": associados_distintos,
        "cartoes_distintos": cartoes_distintos,
    }


def formatar_moeda(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_html(kpis, negocio, qualidade, amostra_linhas, chart_js_source):
    labels_bandeira = json.dumps([r["bandeira_cartao"] for r in negocio])
    valores_bandeira = json.dumps([float(r["valor_total"]) for r in negocio])
    qtd_bandeira = json.dumps([int(r["qtd_movimentacoes"]) for r in negocio])

    pct_invalido = qualidade.get("movimentacoes_invalidas_descartadas_pct", 0)
    metricas_brutas = qualidade.get("metricas_movimentacao_bruta", {})
    pct_duplicados = metricas_brutas.get("percentual_duplicados", 0)
    nulos_por_coluna = metricas_brutas.get("percentual_nulos_por_coluna", {})
    maior_nulo = max(nulos_por_coluna.values()) if nulos_por_coluna else 0

    linhas_tabela_html = ""
    for r in amostra_linhas[:8]:
        linhas_tabela_html += "<tr>" + "".join(
            f"<td>{html_lib.escape(str(r.get(c, '')))}</td>"
            for c in ["nome", "sobrenome", "bandeira_cartao", "tipo_conta",
                      "vlr_transacao_movimento", "data_movimentacao"]
        ) + "</tr>\n"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SiCooperative — Painel de Movimentações</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script>{chart_js_source}</script>
<style>
  :root {{
    --bg: #F7F3EC;
    --ink: #211D18;
    --ink-soft: #5C564C;
    --green: #1F4D3A;
    --gold: #B8862C;
    --rule: #D8D0C0;
    --panel: #FFFDF8;
  }}

  * {{ box-sizing: border-box; }}

  body {{
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: 'Inter', sans-serif;
    line-height: 1.5;
  }}

  .wrap {{
    max-width: 960px;
    margin: 0 auto;
    padding: 56px 32px 80px;
  }}

  header {{
    border-bottom: 2px solid var(--ink);
    padding-bottom: 24px;
    margin-bottom: 40px;
  }}

  .marca {{
    font-family: 'Source Serif 4', serif;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 0.02em;
    color: var(--green);
    margin: 0 0 12px;
  }}

  h1 {{
    font-family: 'Source Serif 4', serif;
    font-weight: 600;
    font-size: clamp(28px, 4vw, 40px);
    margin: 0 0 8px;
    max-width: 34ch;
  }}

  .subtitulo {{
    color: var(--ink-soft);
    font-size: 15px;
    margin: 0;
    max-width: 60ch;
  }}

  .regua-kpi {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    margin-bottom: 48px;
  }}

  .kpi {{
    padding: 24px 20px;
    border-left: 1px solid var(--rule);
  }}
  .kpi:first-child {{ border-left: none; padding-left: 0; }}

  .kpi .valor {{
    font-family: 'Source Serif 4', serif;
    font-weight: 600;
    font-size: 30px;
    color: var(--green);
    display: block;
  }}

  .kpi .rotulo {{
    font-size: 12.5px;
    color: var(--ink-soft);
    margin-top: 4px;
    display: block;
  }}

  section {{ margin-bottom: 52px; }}

  h2 {{
    font-family: 'Source Serif 4', serif;
    font-weight: 600;
    font-size: 20px;
    margin: 0 0 4px;
  }}

  .desc-secao {{
    color: var(--ink-soft);
    font-size: 13.5px;
    margin: 0 0 20px;
  }}

  .painel {{
    background: var(--panel);
    border: 1px solid var(--rule);
    padding: 24px;
  }}

  .qualidade-item {{
    margin-bottom: 18px;
  }}
  .qualidade-item:last-child {{ margin-bottom: 0; }}

  .qualidade-topo {{
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    margin-bottom: 6px;
  }}

  .qualidade-topo .num {{
    font-weight: 600;
    color: var(--green);
  }}

  .barra-fundo {{
    height: 6px;
    background: var(--rule);
  }}

  .barra-preenchida {{
    height: 100%;
    background: var(--gold);
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}

  th {{
    text-align: left;
    font-weight: 600;
    color: var(--ink-soft);
    font-size: 11.5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0 12px 10px;
    border-bottom: 1px solid var(--ink);
  }}

  td {{
    padding: 10px 12px;
    border-bottom: 1px solid var(--rule);
  }}

  tr:last-child td {{ border-bottom: none; }}

  footer {{
    border-top: 1px solid var(--rule);
    padding-top: 20px;
    color: var(--ink-soft);
    font-size: 12px;
  }}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <p class="marca">SICOOPERATIVE</p>
    <h1>Painel de movimentações dos associados</h1>
    <p class="subtitulo">Visão consolidada gerada a partir do pipeline de dados, associados, contas, cartões e movimentações financeiras, com métricas de qualidade aplicadas.</p>
  </header>

  <div class="regua-kpi">
    <div class="kpi">
      <span class="valor">{kpis['total_registros']:,}</span>
      <span class="rotulo">Movimentações válidas</span>
    </div>
    <div class="kpi">
      <span class="valor">{formatar_moeda(kpis['valor_total'])}</span>
      <span class="rotulo">Valor total movimentado</span>
    </div>
    <div class="kpi">
      <span class="valor">{formatar_moeda(kpis['ticket_medio'])}</span>
      <span class="rotulo">Ticket médio</span>
    </div>
    <div class="kpi">
      <span class="valor">{kpis['associados_distintos']:,}</span>
      <span class="rotulo">Associados distintos</span>
    </div>
    <div class="kpi">
      <span class="valor">{kpis['cartoes_distintos']:,}</span>
      <span class="rotulo">Cartões distintos</span>
    </div>
  </div>

  <section>
    <h2>Movimentações por bandeira</h2>
    <p class="desc-secao">Quantidade e valor total movimentado, agrupados por bandeira do cartão.</p>
    <div class="painel">
      <canvas id="graficoBandeira" height="90"></canvas>
    </div>
  </section>

  <section>
    <h2>Qualidade dos dados</h2>
    <p class="desc-secao">Percentuais medidos na etapa de validação do ETL, sobre o dado bruto de movimentação.</p>
    <div class="painel">
      <div class="qualidade-item">
        <div class="qualidade-topo"><span>Movimentações inválidas descartadas (valor ≤ 0)</span><span class="num">{pct_invalido}%</span></div>
        <div class="barra-fundo"><div class="barra-preenchida" style="width:{min(pct_invalido*4, 100)}%"></div></div>
      </div>
      <div class="qualidade-item">
        <div class="qualidade-topo"><span>Registros duplicados detectados</span><span class="num">{pct_duplicados}%</span></div>
        <div class="barra-fundo"><div class="barra-preenchida" style="width:{min(pct_duplicados*4, 100)}%"></div></div>
      </div>
      <div class="qualidade-item">
        <div class="qualidade-topo"><span>Maior percentual de nulos em uma única coluna</span><span class="num">{maior_nulo}%</span></div>
        <div class="barra-fundo"><div class="barra-preenchida" style="width:{min(maior_nulo*4, 100)}%"></div></div>
      </div>
    </div>
  </section>

  <section>
    <h2>Amostra da visão consolidada</h2>
    <p class="desc-secao">Primeiras linhas de movimento_flat.csv, com CPF e sobrenome já anonimizados pelo ETL.</p>
    <div class="painel">
      <table>
        <thead>
          <tr><th>Nome</th><th>Sobrenome</th><th>Bandeira</th><th>Tipo de conta</th><th>Valor</th><th>Data</th></tr>
        </thead>
        <tbody>
          {linhas_tabela_html}
        </tbody>
      </table>
    </div>
  </section>

  <footer>
    Gerado localmente a partir dos arquivos em data/output/.
  </footer>

</div>

<script>
  const ctx = document.getElementById('graficoBandeira');
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: {labels_bandeira},
      datasets: [{{
        label: 'Valor total (R$)',
        data: {valores_bandeira},
        backgroundColor: '#1F4D3A',
        borderRadius: 2,
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ beginAtZero: true, grid: {{ color: '#D8D0C0' }} }},
        x: {{ grid: {{ display: false }} }}
      }}
    }}
  }});
</script>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Gera um dashboard HTML a partir dos arquivos de saída do pipeline.")
    parser.add_argument("--output-dir", type=str, default="data/output",
                         help="Pasta onde estão os arquivos gerados pelo ETL (default: data/output)")
    args = parser.parse_args()

    caminho_flat = os.path.join(args.output_dir, "movimento_flat.csv")
    caminho_negocio = os.path.join(args.output_dir, "analise_negocio_movimentacoes_por_bandeira.csv")
    caminho_qualidade = os.path.join(args.output_dir, "data_quality_report.json")

    for caminho in [caminho_flat, caminho_negocio, caminho_qualidade]:
        if not os.path.exists(caminho):
            print(f"[ERRO] Arquivo não encontrado: {caminho}")
            print("Rode o pipeline (docker compose up --build) antes de gerar o dashboard.")
            return

    linhas_flat = ler_csv(caminho_flat)
    linhas_negocio = ler_csv(caminho_negocio)
    with open(caminho_qualidade, encoding="utf-8") as f:
        qualidade = json.load(f)

    caminho_chartjs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "chart.umd.js")
    with open(caminho_chartjs, encoding="utf-8") as f:
        chart_js_source = f.read()

    kpis = calcular_kpis(linhas_flat)
    html_final = montar_html(kpis, linhas_negocio, qualidade, linhas_flat, chart_js_source)

    caminho_saida = os.path.join(args.output_dir, "dashboard.html")
    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write(html_final)

    print(f"[OK] Dashboard gerado em: {caminho_saida}")
    print("Abra esse arquivo direto no navegador para visualizar.")


if __name__ == "__main__":
    main()
