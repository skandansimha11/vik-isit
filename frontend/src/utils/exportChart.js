import { toPng } from "html-to-image";

export async function exportChartAsPng(node, filename) {
  if (!node) return;
  const dataUrl = await toPng(node, { backgroundColor: "#1a1a1a", pixelRatio: 2 });
  const link = document.createElement("a");
  link.download = filename;
  link.href = dataUrl;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
