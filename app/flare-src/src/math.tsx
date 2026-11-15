/** Rumus dirender dengan KaTeX (dibundel, tanpa CDN). */
import React from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

export function texToHtml(src: string, display = false) {
  try {
    return katex.renderToString(src, { displayMode: display, throwOnError: false, strict: "ignore", output: "html" });
  } catch {
    return src;
  }
}

export function Tex({ src, display = true, caption }: { src: string; display?: boolean; caption?: string }) {
  const html = texToHtml(src, display);
  if (!display) return <span dangerouslySetInnerHTML={{ __html: html }} />;
  return (
    <div className="formula" role="math" aria-label={src}>
      <div dangerouslySetInnerHTML={{ __html: html }} />
      {caption && <span className="formula-caption">{caption}</span>}
    </div>
  );
}

/** "K ≈ 0.111 + 1.8·O2 + 0.611·He" (rumus regresi simbolik) -> LaTeX. */
export function plainFormulaToTex(s: string) {
  return s
    .replace(/≈/g, "\\approx ")
    .replace(/·/g, "\\,")
    .replace(/\bO2\b/g, "X_{\\mathrm{O_2}}")
    .replace(/\bHe\b/g, "X_{\\mathrm{He}}")
    .replace(/\bCO2\b/g, "X_{\\mathrm{CO_2}}");
}

export const TEX = {
  gravity:
    "X_{\\lim}(a) = X_0 + A\\,e^{-a/a_q} + B\\,a,\\qquad U = U_{\\text{forced}} + U_{b1}\\left(\\frac{g}{g_E}\\right)^{n}\\left(\\frac{p_0}{p}\\right)^{n}",
  smoke: "\\ln L_{SP} = a_{\\text{fuel}} + b\\,\\ln u_{\\text{coflow}} + c\\,\\ln d_{\\text{nozzle}} + \\varepsilon_{GP}",
  gpBoundary: "P(\\text{event}\\mid \\mathbf{x}) = \\Phi\\big(f(\\mathbf{x})\\big),\\quad f \\sim \\mathcal{GP}(0, k),\\qquad U(\\mathbf{x}) = \\frac{|\\mu(\\mathbf{x})|}{\\sigma(\\mathbf{x})}",
  score: "s = \\frac{w_d\\,c_{\\text{direct}} + w_c\\,c_{\\text{conditions}} + w_e\\,c_{\\text{evidence}}}{w_d + w_c + w_e}",
  quantile: "\\hat{t}_{\\tau}(\\mathbf{x}),\\ \\tau \\in \\{0.1, 0.5, 0.9\\}\\ \\text{(gradient boosting, per-day conformal)}",
};
