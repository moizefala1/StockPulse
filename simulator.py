import json
import os
from datetime import datetime

from params import log


class Portfolio:
    def __init__(self, initial_cash: float = 150.0, save_path: str = "simulation.json"):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, dict] = {}
        self.closed_trades: list[dict] = []
        self.current_prices: dict[str, float] = {}
        self.save_path = save_path
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path) as f:
                    data = json.load(f)
                self.cash = data.get("cash", self.initial_cash)
                self.positions = data.get("positions", {})
                self.closed_trades = data.get("closed_trades", [])
                self.current_prices = data.get("current_prices", {})
                log.info(
                    f"[SIM] Estado cargado: ${self.cash:.2f} cash, "
                    f"{len(self.positions)} posiciones abiertas, "
                    f"{len(self.closed_trades)} trades cerrados"
                )
            except Exception:
                pass

    def _save(self) -> None:
        with open(self.save_path, "w") as f:
            json.dump(
                {
                    "cash": self.cash,
                    "positions": self.positions,
                    "closed_trades": self.closed_trades,
                    "current_prices": self.current_prices,
                },
                f,
                indent=2,
                default=str,
            )

    def update_price(self, symbol: str, price: float) -> None:
        self.current_prices[symbol] = price

    def on_buy(self, symbol: str, price: float, timestamp: str = "") -> None:
        if symbol in self.positions:
            return

        if price <= 0:
            return

        shares = int(self.cash // price)
        if shares < 1:
            log.info(
                f"[SIM] {symbol}: sin cash para 1 accion "
                f"(precio=${price:.2f}, cash=${self.cash:.2f})"
            )
            return

        cost = shares * price
        self.cash -= cost
        ts = timestamp or datetime.now().isoformat()
        self.positions[symbol] = {
            "shares": shares,
            "entry_price": price,
            "entry_time": ts,
        }
        self._save()
        log.info(
            f"[SIM] BUY  {symbol}: {shares} x ${price:.2f} = ${cost:.2f} | "
            f"cash restante: ${self.cash:.2f}"
        )

    def on_sell(self, symbol: str, price: float, timestamp: str = "") -> None:
        if symbol not in self.positions:
            return

        pos = self.positions.pop(symbol)
        shares = pos["shares"]
        entry_price = pos["entry_price"]
        proceeds = shares * price
        self.cash += proceeds
        pnl = proceeds - (shares * entry_price)
        pnl_pct = (price / entry_price - 1) * 100

        trade = {
            "symbol": symbol,
            "shares": shares,
            "entry_price": entry_price,
            "exit_price": price,
            "entry_time": pos["entry_time"],
            "exit_time": timestamp or datetime.now().isoformat(),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        }
        self.closed_trades.append(trade)
        self._save()
        log.info(
            f"[SIM] SELL {symbol}: {shares} x ${price:.2f} = ${proceeds:.2f} | "
            f"P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%) | cash: ${self.cash:.2f}"
        )

    def close_all(self) -> None:
        for symbol in list(self.positions.keys()):
            price = self.current_prices.get(
                symbol, self.positions[symbol]["entry_price"]
            )
            self.on_sell(symbol, price)

    def open_value(self) -> float:
        return sum(
            self.current_prices.get(sym, pos["entry_price"]) * pos["shares"]
            for sym, pos in self.positions.items()
        )

    def total_value(self) -> float:
        return self.cash + self.open_value()

    def summary(self) -> str:
        total_pnl = sum(t["pnl"] for t in self.closed_trades)
        winning = [t for t in self.closed_trades if t["pnl"] > 0]
        losing = [t for t in self.closed_trades if t["pnl"] <= 0]
        win_rate = (
            len(winning) / len(self.closed_trades) * 100
            if self.closed_trades
            else 0
        )

        best = max(self.closed_trades, key=lambda t: t["pnl"]) if self.closed_trades else None
        worst = min(self.closed_trades, key=lambda t: t["pnl"]) if self.closed_trades else None

        total_val = self.total_value()
        total_return = total_val - self.initial_cash
        total_return_pct = (total_val / self.initial_cash - 1) * 100

        open_val = self.open_value()

        lines = [
            "",
            "=" * 60,
            "  SIMULACION — RESUMEN FINAL",
            "=" * 60,
            f"  Capital inicial:     ${self.initial_cash:>10.2f}",
            f"  Cash disponible:     ${self.cash:>10.2f}",
            f"  Valor pos. abiertas: ${open_val:>10.2f}",
            f"  Valor total:         ${total_val:>10.2f}",
            f"  Retorno total:       ${total_return:>+10.2f} ({total_return_pct:+.2f}%)",
            "",
            f"  Trades cerrados: {len(self.closed_trades)}",
            f"  Ganadores: {len(winning)} | Perdedores: {len(losing)}",
            f"  Win rate: {win_rate:.1f}%",
            f"  P&L acumulado: ${total_pnl:+.2f}",
        ]

        if best:
            lines.append(
                f"  Mejor trade:  {best['symbol']} ${best['pnl']:+.2f} ({best['pnl_pct']:+.2f}%)"
            )
        if worst:
            lines.append(
                f"  Peor trade:   {worst['symbol']} ${worst['pnl']:+.2f} ({worst['pnl_pct']:+.2f}%)"
            )

        if self.positions:
            lines.append("")
            lines.append("  Posiciones abiertas (cerradas al ultimo precio):")
            for sym in sorted(self.positions):
                pos = self.positions[sym]
                last_px = self.current_prices.get(sym, pos["entry_price"])
                unreal_pnl = (last_px - pos["entry_price"]) * pos["shares"]
                unreal_pct = (last_px / pos["entry_price"] - 1) * 100
                lines.append(
                    f"    {sym}: {pos['shares']} x ${pos['entry_price']:.2f} "
                    f"→ ultimo ${last_px:.2f} | "
                    f"no realizado: ${unreal_pnl:+.2f} ({unreal_pct:+.2f}%)"
                )

        if self.closed_trades:
            lines.append("")
            lines.append("  Historial de trades cerrados:")
            for t in self.closed_trades:
                lines.append(
                    f"    {t['symbol']:6s} {t['shares']:3d} x "
                    f"${t['entry_price']:>8.2f} → ${t['exit_price']:>8.2f} | "
                    f"P&L: ${t['pnl']:>+7.2f} ({t['pnl_pct']:>+7.2f}%)"
                )

        lines.append("=" * 60)
        return "\n".join(lines)


_portfolio: Portfolio | None = None


def get_portfolio(initial_cash: float = 150.0) -> Portfolio:
    global _portfolio
    if _portfolio is None:
        _portfolio = Portfolio(initial_cash=initial_cash)
    return _portfolio
