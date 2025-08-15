import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import accounts

# Helpful constants
AAPL = "AAPL"
TSLA = "TSLA"
GOOGL = "GOOGL"

def test_get_share_price_supported_symbols():
    assert accounts.get_share_price("aapl") == Decimal("150.00")
    assert accounts.get_share_price("TSLA") == Decimal("700.00")
    assert accounts.get_share_price(" googl ") == Decimal("2700.00")

def test_get_share_price_invalid_symbol():
    with pytest.raises(accounts.InvalidTransactionError):
        accounts.get_share_price("")
    with pytest.raises(accounts.InvalidTransactionError):
        accounts.get_share_price("UNKNOWN")

def test_deposit_and_withdraw():
    acct = accounts.Account(user_id="user1")
    # Deposit
    tx1 = acct.deposit(Decimal("100.00"), timestamp=datetime(2020,1,1, tzinfo=timezone.utc), note="deposit1")
    assert acct.get_cash_balance() == Decimal("100.00")
    assert tx1.type == "deposit"
    assert Decimal(tx1.amount) == Decimal("100.00")
    # Withdraw
    tx2 = acct.withdraw(Decimal("30.00"), timestamp=datetime(2020,1,2, tzinfo=timezone.utc), note="withdraw1")
    assert acct.get_cash_balance() == Decimal("70.00")
    assert tx2.type == "withdraw"

def test_initial_deposit_recorded():
    ts = datetime(2021,5,1, tzinfo=timezone.utc)
    acct = accounts.Account(user_id="user_init", initial_deposit=Decimal("250.00"), timestamp=ts)
    assert acct.get_cash_balance() == Decimal("250.00")
    # Ledger should contain the initial deposit as first transaction
    txs = acct.list_transactions()
    assert len(txs) == 1
    assert txs[0].note == "initial_deposit"
    assert txs[0].type == "deposit"

def test_withdraw_insufficient_funds():
    acct = accounts.Account(user_id="user2")
    acct.deposit(Decimal("10.00"))
    with pytest.raises(accounts.InsufficientFundsError):
        acct.withdraw(Decimal("20.00"))

def test_deposit_invalid_amount_type():
    acct = accounts.Account(user_id="user3")
    with pytest.raises(accounts.InvalidTransactionError):
        acct.deposit(100.0)  # not a Decimal

def test_buy_with_sufficient_cash():
    acct = accounts.Account(user_id="buyer")
    acct.deposit(Decimal("1000.00"))
    tx = acct.buy(AAPL, 2)
    # 2 * 150 = 300.00
    assert acct.get_cash_balance() == Decimal("700.00")
    holdings = acct.get_holdings()
    assert holdings.get("AAPL") == 2
    assert tx.type == "buy"
    assert tx.symbol == "AAPL"
    assert tx.quantity == 2
    assert tx.price_per_share == Decimal("150.00")

def test_buy_insufficient_funds():
    acct = accounts.Account(user_id="buyer2")
    acct.deposit(Decimal("100.00"))
    with pytest.raises(accounts.InsufficientFundsError):
        acct.buy(TSLA, 1)  # TSLA is 700.00

def test_sell_with_sufficient_shares():
    acct = accounts.Account(user_id="seller")
    acct.deposit(Decimal("2000.00"))
    acct.buy(TSLA, 1)  # cost 700
    before_cash = acct.get_cash_balance()
    tx = acct.sell(TSLA, 1)
    # cash should increase back
    assert acct.get_cash_balance() == before_cash + Decimal("700.00")
    assert acct.get_holdings().get("TSLA") is None
    assert tx.type == "sell"
    assert tx.symbol == "TSLA"

def test_sell_insufficient_shares():
    acct = accounts.Account(user_id="seller2")
    with pytest.raises(accounts.InsufficientSharesError):
        acct.sell(AAPL, 1)

def test_transaction_serialization_roundtrip():
    acct = accounts.Account(user_id="ser")
    tx = acct.deposit(Decimal("50.00"), timestamp=datetime(2022,3,3, tzinfo=timezone.utc), note="note")
    d = tx.to_dict()
    tx2 = accounts.Transaction.from_dict(d)
    assert tx.id == tx2.id
    assert tx.type == tx2.type
    assert tx.amount == tx2.amount
    assert tx.timestamp == tx2.timestamp
    assert tx.note == tx2.note

def test_account_to_from_dict_roundtrip():
    acct = accounts.Account(user_id="round", initial_deposit=Decimal("100.00"))
    acct.deposit(Decimal("50.00"))
    acct.buy(AAPL, 1)
    d = acct.to_dict()
    acct2 = accounts.Account.from_dict(d)
    assert acct2.user_id == acct.user_id
    assert acct2.get_cash_balance() == acct.get_cash_balance()
    assert acct2.get_holdings() == acct.get_holdings()
    # ledger lengths should match
    assert len(acct2.list_transactions()) == len(acct.list_transactions())

def test_list_transactions_filtering():
    acct = accounts.Account(user_id="filter")
    t1 = datetime(2020,1,1, tzinfo=timezone.utc)
    t2 = datetime(2020,6,1, tzinfo=timezone.utc)
    t3 = datetime(2020,12,1, tzinfo=timezone.utc)
    tx1 = acct.deposit(Decimal("10.00"), timestamp=t1)
    tx2 = acct.deposit(Decimal("20.00"), timestamp=t2)
    tx3 = acct.withdraw(Decimal("5.00"), timestamp=t3)
    # filter start_time
    res = acct.list_transactions(start_time=datetime(2020,5,1, tzinfo=timezone.utc))
    assert tx1 not in res
    assert tx2 in res
    assert tx3 in res
    # filter by type
    deposits = acct.list_transactions(types=["deposit"])
    assert all(tx.type == "deposit" for tx in deposits)

def test_get_transaction_lookup():
    acct = accounts.Account(user_id="lookup")
    tx = acct.deposit(Decimal("15.00"))
    found = acct.get_transaction(tx.id)
    assert found.id == tx.id
    with pytest.raises(accounts.InvalidTransactionError):
        acct.get_transaction("nonexistent")

def test_portfolio_and_total_equity():
    acct = accounts.Account(user_id="portfolio")
    acct.deposit(Decimal("5000.00"))
    acct.buy(GOOGL, 1)  # cost 2700
    portfolio = acct.get_portfolio_value()
    assert portfolio == Decimal("2700.00")
    total = acct.get_total_equity()
    # cash 5000 - 2700 = 2300, equity = 2300 + 2700 = 5000
    assert total == Decimal("5000.00")

def test_profit_loss_calculations():
    acct = accounts.Account(user_id="pnl", initial_deposit=Decimal("1000.00"))
    acct.deposit(Decimal("500.00"))
    acct.buy(AAPL, 2)  # -300
    # initial_deposit = 1000.00
    # total_deposits = 1500.00
    equity = acct.get_total_equity()
    pnl_initial = acct.get_profit_loss_from_initial()
    pnl_net = acct.get_profit_loss_from_net_deposits()
    assert equity == acct.get_total_equity()
    # pnl_initial = equity - 1000.00
    assert pnl_initial == equity - Decimal("1000.00")
    # pnl_net = equity - (total_deposits - total_withdrawals)
    net_deposits = Decimal(acct.to_dict()["total_deposits"])  # string
    net_deposits = Decimal(net_deposits)
    assert pnl_net == equity - Decimal(str(net_deposits))