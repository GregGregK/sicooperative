import argparse
import json
import os


def classificar_severidade(percentual):
    """Retorna (cor, rotulo) conforme faixas de severidade do percentual."""
    if percentual < 5:
        return "#1F4D3A", "OK"          # verde
    elif percentual < 15:
        return "#B8862C", "ATENÇÃO"     # dourado/âmbar
    else:
        return "#B23A2E", "CRÍTICO"     # vermelho


def montar_html(qualidade, chart_js_source):
    metricas_brutas = qualidade.get("metricas_movimentacao_bruta", {})
    total_registros = metricas_brutas.get("total_registros", 0)
    pct_invalido = qualidade.get("movimentacoes_invalidas_descartadas_pct", 0)
    pct_duplicados = metricas_brutas.get("percentual_duplicados", 0)
    total_duplicados = metricas_brutas.get("total_duplicados", 0)
    nulos_por_coluna = metricas_brutas.get("percentual_nulos_por_coluna", {})

    # Ordena colunas da pior (mais nulos) para a melhor, para o gráfico
    colunas_ordenadas = sorted(nulos_por_coluna.items(), key=lambda x: x[1], reverse=True)
    labels_colunas = json.dumps([c for c, _ in colunas_ordenadas])
    valores_colunas = json.dumps([v for _, v in colunas_ordenadas])
    cores_colunas = json.dumps([classificar_severidade(v)[0] for _, v in colunas_ordenadas])

    cor_invalido, rotulo_invalido = classificar_severidade(pct_invalido)
    cor_duplicado, rotulo_duplicado = classificar_severidade(pct_duplicados)

    pior_coluna = colunas_ordenadas[0] if colunas_ordenadas else ("—", 0)

    linhas_tabela = ""
    for coluna, pct in colunas_ordenadas:
        cor, rotulo = classificar_severidade(pct)
        linhas_tabela += f"""<tr>
            <td>{coluna}</td>
            <td>{pct}%</td>
            <td><span class="tag" style="background:{cor}22;color:{cor}">{rotulo}</span></td>
        </tr>\n"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SiCooperative — Painel de Qualidade dos Dados</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #F7F3EC;
    --ink: #211D18;
    --ink-soft: #5C564C;
    --green: #1F4D3A;
    --gold: #B8862C;
    --red: #B23A2E;
    --rule: #D8D0C0;
    --panel: #FFFDF8;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: 'Inter', sans-serif; line-height: 1.5; }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 56px 32px 80px; }}
  header {{ border-bottom: 2px solid var(--ink); padding-bottom: 24px; margin-bottom: 40px; }}
  .marca {{ font-family: 'Source Serif 4', serif; font-weight: 700; font-size: 15px; letter-spacing: 0.02em; color: var(--green); margin: 0 0 12px; }}
  h1 {{ font-family: 'Source Serif 4', serif; font-weight: 600; font-size: clamp(28px, 4vw, 40px); margin: 0 0 8px; max-width: 34ch; }}
  .subtitulo {{ color: var(--ink-soft); font-size: 15px; margin: 0; max-width: 60ch; }}

  .regua-kpi {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); margin-bottom: 48px; }}
  .kpi {{ padding: 24px 20px; border-left: 1px solid var(--rule); }}
  .kpi:first-child {{ border-left: none; padding-left: 0; }}
  .kpi .valor {{ font-family: 'Source Serif 4', serif; font-weight: 600; font-size: 30px; display: block; }}
  .kpi .rotulo {{ font-size: 12.5px; color: var(--ink-soft); margin-top: 4px; display: block; }}

  section {{ margin-bottom: 52px; }}
  h2 {{ font-family: 'Source Serif 4', serif; font-weight: 600; font-size: 20px; margin: 0 0 4px; }}
  .desc-secao {{ color: var(--ink-soft); font-size: 13.5px; margin: 0 0 20px; }}
  .painel {{ background: var(--panel); border: 1px solid var(--rule); padding: 24px; }}

  .duas-colunas {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 640px) {{ .duas-colunas {{ grid-template-columns: 1fr; }} }}

  .destaque-metrica .num-grande {{ font-family: 'Source Serif 4', serif; font-size: 44px; font-weight: 600; line-height: 1; }}
  .destaque-metrica .legenda {{ font-size: 13px; color: var(--ink-soft); margin-top: 8px; }}
  .tag {{ display: inline-block; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 600; letter-spacing: 0.03em; margin-top: 12px; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; font-weight: 600; color: var(--ink-soft); font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.04em; padding: 0 12px 10px; border-bottom: 1px solid var(--ink); }}
  td {{ padding: 10px 12px; border-bottom: 1px solid var(--rule); }}
  tr:last-child td {{ border-bottom: none; }}

  footer {{ border-top: 1px solid var(--rule); padding-top: 20px; color: var(--ink-soft); font-size: 12px; }}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <p class="marca">SICOOPERATIVE</p>
    <h1>Painel de qualidade dos dados</h1>
    <p class="subtitulo">Métricas coletadas na etapa de validação do ETL, sobre o dado bruto de movimentação — antes de qualquer filtro ou correção ser aplicado.</p>
  </header>

  <div class="regua-kpi">
    <div class="kpi">
      <span class="valor">{total_registros:,}</span>
      <span class="rotulo">Registros brutos analisados</span>
    </div>
    <div class="kpi">
      <span class="valor" style="color:{cor_invalido}">{pct_invalido}%</span>
      <span class="rotulo">Inválidos (valor ≤ 0)</span>
    </div>
    <div class="kpi">
      <span class="valor" style="color:{cor_duplicado}">{pct_duplicados}%</span>
      <span class="rotulo">Duplicados ({total_duplicados} registros)</span>
    </div>
    <div class="kpi">
      <span class="valor">{pior_coluna[1]}%</span>
      <span class="rotulo">Pior coluna: {pior_coluna[0]}</span>
    </div>
  </div>

  <section>
    <h2>Integridade e duplicidade</h2>
    <p class="desc-secao">Percentual descartado por validação de integridade, e percentual de linhas duplicadas encontradas no dado bruto.</p>
    <div class="duas-colunas">
      <div class="painel destaque-metrica">
        <span class="num-grande" style="color:{cor_invalido}">{pct_invalido}%</span>
        <p class="legenda">das movimentações tinham valor menor ou igual a zero, e foram descartadas antes de qualquer análise.</p>
        <span class="tag" style="background:{cor_invalido}22;color:{cor_invalido}">{rotulo_invalido}</span>
      </div>
      <div class="painel destaque-metrica">
        <span class="num-grande" style="color:{cor_duplicado}">{pct_duplicados}%</span>
        <p class="legenda">dos registros ({total_duplicados} no total) são duplicatas exatas de cartão + valor + descrição + data.</p>
        <span class="tag" style="background:{cor_duplicado}22;color:{cor_duplicado}">{rotulo_duplicado}</span>
      </div>
    </div>
  </section>

  <section>
    <h2>Nulos por coluna</h2>
    <p class="desc-secao">Percentual de valores nulos encontrados em cada coluna da tabela de movimentação bruta.</p>
    <div class="painel">
      <canvas id="graficoNulos" height="{max(120, len(colunas_ordenadas) * 40)}"></canvas>
    </div>
  </section>

  <section>
    <h2>Detalhe por coluna</h2>
    <p class="desc-secao">Mesmos dados do gráfico acima, em formato de tabela, com classificação de severidade.</p>
    <div class="painel">
      <table>
        <thead><tr><th>Coluna</th><th>% de nulos</th><th>Status</th></tr></thead>
        <tbody>
          {linhas_tabela}
        </tbody>
      </table>
    </div>
  </section>

  <footer>
    Classificação de severidade: abaixo de 5% = OK, entre 5% e 15% = Atenção, acima de 15% = Crítico. Gerado localmente a partir de data_quality_report.json — apenas para demonstração.
  </footer>

</div>

<script>{chart_js_source}</script>
<script>
  const ctx = document.getElementById('graficoNulos');
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: {labels_colunas},
      datasets: [{{
        label: '% de nulos',
        data: {valores_colunas},
        backgroundColor: {cores_colunas},
        borderRadius: 2,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ beginAtZero: true, grid: {{ color: '#D8D0C0' }} }},
        y: {{ grid: {{ display: false }} }}
      }}
    }}
  }});
</script>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Gera um dashboard HTML dedicado à qualidade dos dados.")
    parser.add_argument("--output-dir", type=str, default="data/output",
                         help="Pasta onde está o data_quality_report.json (default: data/output)")
    args = parser.parse_args()

    caminho_qualidade = os.path.join(args.output_dir, "data_quality_report.json")
    if not os.path.exists(caminho_qualidade):
        print(f"[ERRO] Arquivo não encontrado: {caminho_qualidade}")
        print("Rode o pipeline (docker compose up --build) antes de gerar o dashboard.")
        return

    with open(caminho_qualidade, encoding="utf-8") as f:
        qualidade = json.load(f)

    caminho_chartjs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "chart.umd.js")
    with open(caminho_chartjs, encoding="utf-8") as f:
        chart_js_source = f.read()

    html_final = montar_html(qualidade, chart_js_source)

    caminho_saida = os.path.join(args.output_dir, "dashboard_qualidade.html")
    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write(html_final)

    print(f"[OK] Dashboard de qualidade gerado em: {caminho_saida}")
    print("Abra esse arquivo direto no navegador para visualizar.")


if __name__ == "__main__":
    main()