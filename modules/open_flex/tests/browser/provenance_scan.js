(() => {
  const UNIT = /(\d[\d.,]*\s?(µm|um|mm²\/s|mm\^2\/s|mm²|mmHg|mm|atm|L\b|s\b|%|K\b|Hz|fps|px\/mm|kg|°C))/;
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const t = n.textContent.trim();
    if (!t || !UNIT.test(t)) continue;
    const el = n.parentElement;
    if (el.closest("script,style,.js-plotly-plot,option,select,svg")) continue;
    if (el.closest("[data-claims],[data-interpretive],[data-source],[data-derived]")) continue;
    const tab = el.closest("main"); 
    out.push((tab ? tab.id : "-") + " | " + t.slice(0, 110));
  }
  return out;
})()
