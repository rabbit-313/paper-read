const input = document.querySelector("#paper-search");
const cards = Array.from(document.querySelectorAll(".paper-card"));

input?.addEventListener("input", () => {
  const query = input.value.trim().toLowerCase();
  for (const card of cards) {
    const haystack = `${card.textContent} ${card.dataset.search}`.toLowerCase();
    card.hidden = query.length > 0 && !haystack.includes(query);
  }
});
