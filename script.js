const input = document.querySelector("#paper-search");
const cards = Array.from(document.querySelectorAll(".paper-card"));
const recommendationList = document.querySelector("#recommendation-list");
const recommendationStatus = document.querySelector("#recommendation-status");

input?.addEventListener("input", () => {
  const query = input.value.trim().toLowerCase();
  for (const card of cards) {
    const haystack = `${card.textContent} ${card.dataset.search}`.toLowerCase();
    card.hidden = query.length > 0 && !haystack.includes(query);
  }
});

async function loadRecommendations() {
  if (!recommendationList || !recommendationStatus) return;
  try {
    const response = await fetch("./recommendations/latest.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const items = Array.isArray(data.items) ? data.items : [];
    recommendationStatus.textContent = items.length
      ? `${data.date || "Latest"} / ${items.length} candidates`
      : "No recommendation candidates yet.";
    recommendationList.replaceChildren(...items.map(renderRecommendation));
  } catch (error) {
    recommendationStatus.textContent =
      "推薦データはまだ生成されていません。GitHub Actions の daily workflow 実行後に表示されます。";
  }
}

function renderRecommendation(item) {
  const article = document.createElement("article");
  article.className = "recommendation-card";

  const meta = document.createElement("div");
  meta.className = "paper-meta";
  meta.append(
    textBadge(item.source || "source"),
    textBadge(item.published || "date unknown"),
    textBadge(`score ${item.score ?? "-"}`),
  );

  const title = document.createElement("h3");
  title.textContent = item.title || "Untitled";

  const summary = document.createElement("p");
  summary.textContent = item.summary || "要約はまだありません。";

  const reasons = document.createElement("div");
  reasons.className = "reason-list";
  for (const reason of item.reasons || []) {
    reasons.append(textBadge(reason));
  }

  const actions = document.createElement("div");
  actions.className = "actions";
  if (item.url) {
    const paperLink = document.createElement("a");
    paperLink.href = item.url;
    paperLink.textContent = "論文を見る";
    paperLink.target = "_blank";
    paperLink.rel = "noreferrer";
    actions.append(paperLink);
  }
  if (item.requestUrl) {
    const requestLink = document.createElement("a");
    requestLink.href = item.requestUrl;
    requestLink.textContent = "翻訳とスライドを依頼";
    requestLink.target = "_blank";
    requestLink.rel = "noreferrer";
    actions.append(requestLink);
  }

  article.append(meta, title, summary, reasons, actions);
  return article;
}

function textBadge(value) {
  const span = document.createElement("span");
  span.textContent = value;
  return span;
}

loadRecommendations();
