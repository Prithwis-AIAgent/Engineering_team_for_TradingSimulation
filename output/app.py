# app.py
import gradio as gr
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from accounts import Account, get_share_price, AccountError


# Helper formatters
def _fmt_money(amount: Decimal, currency: str = "USD") -> str:
    return f"{amount:.2f} {currency}"


def _empty_snapshot() -> Tuple[
    str, str, Dict[str, int], str, str, List[Dict[str, Any]]
]:
    return (
        "No account exists. Create an account to begin.",
        "0.00 USD",
        {},
        "0.00 USD",
        "0.00 USD",
        [],
    )


def snapshot_for_account(
    acct: Account,
) -> Tuple[str, str, Dict[str, int], str, str, List[Dict[str, Any]]]:
    cash = acct.get_cash_balance()
    holdings = acct.get_holdings()
    portfolio = acct.get_portfolio_value()
    total_equity = acct.get_total_equity()
    profit_initial = acct.get_profit_loss_from_initial()
    txs = [tx.to_dict() for tx in acct.list_transactions()]
    status = f"Account '{acct.user_id}' loaded. Cash: {_fmt_money(cash, acct.currency)}"
    return (
        status,
        _fmt_money(cash, acct.currency),
        holdings,
        _fmt_money(total_equity, acct.currency),
        _fmt_money(profit_initial, acct.currency),
        txs,
    )


# Core actions
def create_account(
    user_id: str, initial_deposit: str, state: Optional[Account]
) -> Tuple[str, str, Dict[str, int], str, str, List[Dict[str, Any]], Optional[Account]]:
    if not user_id or not isinstance(user_id, str) or user_id.strip() == "":
        return (
            ("Error: user_id must be a non-empty string.",)
            + _empty_snapshot()
            + (state,)
        )

    try:
        deposit_val = (
            Decimal(initial_deposit)
            if initial_deposit not in (None, "")
            else Decimal("0.00")
        )
    except (InvalidOperation, TypeError):
        return (
            ("Error: initial deposit must be a valid number (e.g., 1000.00).",)
            + _empty_snapshot()
            + (state,)
        )

    try:
        acct = Account(user_id=user_id.strip(), initial_deposit=deposit_val)
        status, cash, holdings, portfolio, profit, txs = snapshot_for_account(acct)
        return (
            f"Account created for '{acct.user_id}' with initial deposit {_fmt_money(acct.get_cash_balance(), acct.currency)}.",
            cash,
            holdings,
            portfolio,
            profit,
            txs,
            acct,
        )
    except AccountError as e:
        return (f"Error creating account: {str(e)}",) + _empty_snapshot() + (state,)
    except Exception as e:
        return (
            (f"Unexpected error creating account: {str(e)}",)
            + _empty_snapshot()
            + (state,)
        )


def deposit(
    amount: str, note: str, state: Optional[Account]
) -> Tuple[str, str, Dict[str, int], str, str, List[Dict[str, Any]], Optional[Account]]:
    if state is None:
        return (
            ("No account found. Create an account first.",)
            + _empty_snapshot()
            + (state,)
        )
    try:
        amt = Decimal(amount)
    except (InvalidOperation, TypeError):
        return (
            ("Invalid deposit amount. Use a numeric value like 100.00.",)
            + snapshot_for_account(state)
            + (state,)
        )
    try:
        tx = state.deposit(amt, note=note or None)
        status, cash, holdings, portfolio, profit, txs = snapshot_for_account(state)
        return (
            f"Deposit successful: {tx.id}",
            cash,
            holdings,
            portfolio,
            profit,
            txs,
            state,
        )
    except AccountError as e:
        return (f"Deposit error: {str(e)}",) + snapshot_for_account(state) + (state,)
    except Exception as e:
        return (
            (f"Unexpected deposit error: {str(e)}",)
            + snapshot_for_account(state)
            + (state,)
        )


def withdraw(
    amount: str, note: str, state: Optional[Account]
) -> Tuple[str, str, Dict[str, int], str, str, List[Dict[str, Any]], Optional[Account]]:
    if state is None:
        return (
            ("No account found. Create an account first.",)
            + _empty_snapshot()
            + (state,)
        )
    try:
        amt = Decimal(amount)
    except (InvalidOperation, TypeError):
        return (
            ("Invalid withdrawal amount. Use a numeric value like 50.00.",)
            + snapshot_for_account(state)
            + (state,)
        )
    try:
        tx = state.withdraw(amt, note=note or None)
        status, cash, holdings, portfolio, profit, txs = snapshot_for_account(state)
        return (
            f"Withdrawal successful: {tx.id}",
            cash,
            holdings,
            portfolio,
            profit,
            txs,
            state,
        )
    except AccountError as e:
        return (f"Withdrawal error: {str(e)}",) + snapshot_for_account(state) + (state,)
    except Exception as e:
        return (
            (f"Unexpected withdrawal error: {str(e)}",)
            + snapshot_for_account(state)
            + (state,)
        )


def buy(
    symbol: str, quantity: int, note: str, state: Optional[Account]
) -> Tuple[str, str, Dict[str, int], str, str, List[Dict[str, Any]], Optional[Account]]:
    if state is None:
        return (
            ("No account found. Create an account first.",)
            + _empty_snapshot()
            + (state,)
        )
    if not symbol or symbol.strip() == "":
        return ("Symbol is required to buy.",) + snapshot_for_account(state) + (state,)
    try:
        qty = int(quantity)
    except (ValueError, TypeError):
        return (
            ("Quantity must be a positive integer.",)
            + snapshot_for_account(state)
            + (state,)
        )
    try:
        tx = state.buy(symbol, qty, price_lookup=get_share_price, note=note or None)
        status, cash, holdings, portfolio, profit, txs = snapshot_for_account(state)
        return (
            f"Buy successful: {tx.id} — Bought {qty} {tx.symbol} at {tx.price_per_share}",
            cash,
            holdings,
            portfolio,
            profit,
            txs,
            state,
        )
    except AccountError as e:
        return (f"Buy error: {str(e)}",) + snapshot_for_account(state) + (state,)
    except Exception as e:
        return (
            (f"Unexpected buy error: {str(e)}",)
            + snapshot_for_account(state)
            + (state,)
        )


def sell(
    symbol: str, quantity: int, note: str, state: Optional[Account]
) -> Tuple[str, str, Dict[str, int], str, str, List[Dict[str, Any]], Optional[Account]]:
    if state is None:
        return (
            ("No account found. Create an account first.",)
            + _empty_snapshot()
            + (state,)
        )
    if not symbol or symbol.strip() == "":
        return ("Symbol is required to sell.",) + snapshot_for_account(state) + (state,)
    try:
        qty = int(quantity)
    except (ValueError, TypeError):
        return (
            ("Quantity must be a positive integer.",)
            + snapshot_for_account(state)
            + (state,)
        )
    try:
        tx = state.sell(symbol, qty, price_lookup=get_share_price, note=note or None)
        status, cash, holdings, portfolio, profit, txs = snapshot_for_account(state)
        return (
            f"Sell successful: {tx.id} — Sold {qty} {tx.symbol} at {tx.price_per_share}",
            cash,
            holdings,
            portfolio,
            profit,
            txs,
            state,
        )
    except AccountError as e:
        return (f"Sell error: {str(e)}",) + snapshot_for_account(state) + (state,)
    except Exception as e:
        return (
            (f"Unexpected sell error: {str(e)}",)
            + snapshot_for_account(state)
            + (state,)
        )


def refresh(
    state: Optional[Account],
) -> Tuple[str, str, Dict[str, int], str, str, List[Dict[str, Any]], Optional[Account]]:
    if state is None:
        return (
            ("No account exists. Create one to begin.",) + _empty_snapshot() + (state,)
        )
    try:
        status, cash, holdings, portfolio, profit, txs = snapshot_for_account(state)
        return (status, cash, holdings, portfolio, profit, txs, state)
    except Exception as e:
        return (f"Error refreshing snapshot: {str(e)}",) + _empty_snapshot() + (state,)


# Build Gradio UI
with gr.Blocks() as demo:
    gr.Markdown("# Trading Simulation - Simple Account Demo")
    gr.Markdown(
        "Supported symbols for this demo: AAPL (150.00), TSLA (700.00), GOOGL (2700.00)."
    )

    state = gr.State(None)  # will hold Account object

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("## Account controls")

            with gr.Accordion("Create account", open=True):
                create_user = gr.Textbox(label="User ID", value="demo_user")
                create_initial = gr.Textbox(
                    label="Initial deposit (e.g., 1000.00)", value="1000.00"
                )
                create_btn = gr.Button("Create Account")

            with gr.Accordion("Cash operations", open=False):
                deposit_amount = gr.Textbox(
                    label="Deposit amount (e.g., 200.00)", value="100.00"
                )
                deposit_note = gr.Textbox(label="Note (optional)", value="")
                deposit_btn = gr.Button("Deposit")

                withdraw_amount = gr.Textbox(
                    label="Withdraw amount (e.g., 50.00)", value="50.00"
                )
                withdraw_note = gr.Textbox(label="Note (optional)", value="")
                withdraw_btn = gr.Button("Withdraw")

            with gr.Accordion("Trading (buy/sell)", open=False):
                buy_symbol = gr.Textbox(
                    label="Symbol to buy (AAPL/TSLA/GOOGL)", value="AAPL"
                )
                buy_qty = gr.Number(label="Quantity", value=1, precision=0)
                buy_note = gr.Textbox(label="Note (optional)", value="")
                buy_btn = gr.Button("Buy shares")

                sell_symbol = gr.Textbox(
                    label="Symbol to sell (AAPL/TSLA/GOOGL)", value="AAPL"
                )
                sell_qty = gr.Number(label="Quantity", value=1, precision=0)
                sell_note = gr.Textbox(label="Note (optional)", value="")
                sell_btn = gr.Button("Sell shares")

            refresh_btn = gr.Button("Refresh snapshot")

        with gr.Column(scale=3):
            gr.Markdown("## Account snapshot")

            status_out = gr.Textbox(label="Status / Messages", interactive=False)
            cash_out = gr.Textbox(label="Cash balance", interactive=False)
            holdings_out = gr.JSON(label="Holdings (symbol -> quantity)")
            portfolio_out = gr.Textbox(
                label="Total equity (cash + holdings)", interactive=False
            )
            profit_out = gr.Textbox(
                label="Profit/Loss from initial deposit", interactive=False
            )
            tx_out = gr.JSON(label="Transactions (most recent last)")

    # Wire event handlers
    create_btn.click(
        fn=create_account,
        inputs=[create_user, create_initial, state],
        outputs=[
            status_out,
            cash_out,
            holdings_out,
            portfolio_out,
            profit_out,
            tx_out,
            state,
        ],
    )
    deposit_btn.click(
        fn=deposit,
        inputs=[deposit_amount, deposit_note, state],
        outputs=[
            status_out,
            cash_out,
            holdings_out,
            portfolio_out,
            profit_out,
            tx_out,
            state,
        ],
    )
    withdraw_btn.click(
        fn=withdraw,
        inputs=[withdraw_amount, withdraw_note, state],
        outputs=[
            status_out,
            cash_out,
            holdings_out,
            portfolio_out,
            profit_out,
            tx_out,
            state,
        ],
    )
    buy_btn.click(
        fn=buy,
        inputs=[buy_symbol, buy_qty, buy_note, state],
        outputs=[
            status_out,
            cash_out,
            holdings_out,
            portfolio_out,
            profit_out,
            tx_out,
            state,
        ],
    )
    sell_btn.click(
        fn=sell,
        inputs=[sell_symbol, sell_qty, sell_note, state],
        outputs=[
            status_out,
            cash_out,
            holdings_out,
            portfolio_out,
            profit_out,
            tx_out,
            state,
        ],
    )
    refresh_btn.click(
        fn=refresh,
        inputs=[state],
        outputs=[
            status_out,
            cash_out,
            holdings_out,
            portfolio_out,
            profit_out,
            tx_out,
            state,
        ],
    )

    # Initialize UI with empty snapshot
    init_status, init_cash, init_holdings, init_portfolio, init_profit, init_txs = (
        _empty_snapshot()
    )
    status_out.value = init_status
    cash_out.value = init_cash
    holdings_out.value = init_holdings
    portfolio_out.value = init_portfolio
    profit_out.value = init_profit
    tx_out.value = init_txs

if __name__ == "__main__":
    demo.launch()
