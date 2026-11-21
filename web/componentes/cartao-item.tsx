import { marcarLido, marcarSalvo } from "@/app/acoes";
import {
  formatarData,
  linhaDados,
  linkExtra,
  linkSeguro,
  prazoUrgente,
  textoPrazo,
} from "@/lib/formato";
import type { Item } from "@/lib/tipos";

function corNota(nota: number): string {
  if (nota >= 8) return "nota alta";
  if (nota >= 6) return "nota media";
  return "nota baixa";
}

/** Um item do feed. O React escapa todo o texto; links só se forem http(s). */
export function CartaoItem({ item, hoje }: { item: Item; hoje: string }) {
  const url = linkSeguro(item.url);
  const dados = linhaDados(item);
  const extra = linkExtra(item);
  const data = formatarData(item.publicado_em ?? item.coletado_em);
  const mostraNota = item.modulo !== "concursos" && item.nota !== null;

  return (
    <article className={item.lido ? "item lido" : "item"}>
      <header>
        {mostraNota && <span className={corNota(item.nota ?? 0)}>{item.nota}</span>}
        <h3>
          {url ? (
            <a href={url} target="_blank" rel="noopener noreferrer">
              {item.titulo}
            </a>
          ) : (
            item.titulo
          )}
        </h3>
      </header>

      <p className="meta">
        {item.fonte}
        {data && ` · ${data}`}
        {item.salvo && " · ★ salvo"}
      </p>
      {dados && <p className="dados">{dados}</p>}
      {item.prazo && (
        <p className={prazoUrgente(item.prazo, hoje) ? "prazo urgente" : "prazo"}>
          Inscrição: {textoPrazo(item.prazo, hoje)}
        </p>
      )}
      {item.resumo && <p>{item.resumo}</p>}
      {item.tags && item.tags.length > 0 && (
        <p className="tags">
          {item.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </p>
      )}

      <footer>
        {extra && (
          <a href={extra.url} target="_blank" rel="noopener noreferrer">
            {extra.rotulo}
          </a>
        )}
        <form action={marcarLido}>
          <input type="hidden" name="id" value={item.id} />
          <input type="hidden" name="valor" value={item.lido ? "0" : "1"} />
          <button type="submit">{item.lido ? "Marcar não lido" : "Marcar lido"}</button>
        </form>
        <form action={marcarSalvo}>
          <input type="hidden" name="id" value={item.id} />
          <input type="hidden" name="valor" value={item.salvo ? "0" : "1"} />
          <button type="submit">{item.salvo ? "Tirar dos salvos" : "Salvar"}</button>
        </form>
      </footer>
    </article>
  );
}
