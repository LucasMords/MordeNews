/**
 * Para onde voltar depois do login. Só caminhos internos ("/..."): "//site.com" ou
 * "https://..." virariam um redirecionamento aberto para fora do portal.
 */
export function destinoSeguro(valor: unknown): string {
  if (typeof valor !== "string" || !valor.startsWith("/")) return "/";
  if (valor.startsWith("//") || valor.startsWith("/\\") || valor.includes("\n")) return "/";
  return valor.slice(0, 500);
}
