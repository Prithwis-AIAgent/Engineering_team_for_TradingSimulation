# Design for accounts.py — Account management for trading simulation

This document is a detailed design specification for the Python module accounts.py. The module implements a single class Account and supporting types and functions to manage a trading simulation account. The design is meant to be complete and actionable for backend development: it specifies classes, method signatures, internal state, invariants, transaction formats, error types, validation rules, and a simple test implementation of get_share_price(symbol).

Note: monetary values are handled with Decimal internally to avoid floating point rounding. All timestamps are timezone-aware UTC datetimes.

---

## Top-level module summary

- Module name: accounts.py
- Primary class: Account
- Supporting datatypes: Transaction (dataclass), TransactionType (Enum or str constants)
- Exceptions: InsufficientFundsError, InsufficientSharesError, InvalidTransactionError
- Helper function (test price oracle): get_share_price(symbol: str) -> Decimal
- Thread-safety: Account optionally uses a threading.Lock for concurrent usage
- Storage: in-memory ledger (list of Transaction), holdings (dict symbol -> int), cash balance (Decimal)
- Currency: single-currency accounts; currency string stored on account

---

## Imports (for implementation)

- from dataclasses import dataclass, field
- from datetime import datetime, timezone
- from decimal import Decimal, getcontext, ROUND_HALF_UP
- from typing import Optional, Callable, Dict, List, Any
- import uuid
- import threading
- enum for transaction types or simple constant strings

Set Decimal context to at least 2 decimal places for currency. Example: getcontext().prec = 28 and quantize currency values to Decimal("0.01") when storing.

---

## Public behavior overview

- Create account (Account(...)) with optional initial_deposit.
- deposit(amount)
- withdraw(amount) — cannot withdraw more cash than available (no negative cash allowed).
- buy(symbol, quantity) — uses price lookup to compute cost; cannot buy if cash insufficient.
- sell(symbol, quantity) — cannot sell more shares than held.
- get_holdings() -> mapping symbol -> quantity
- get_cash_balance() -> Decimal
- get_portfolio_value(price_lookup: Optional[Callable]) -> Decimal
- get_total_equity(price_lookup: Optional[Callable]) -> Decimal
- get_profit_loss_from_initial(price_lookup: Optional[Callable]) -> Decimal
- get_profit_loss_from_net_deposits(price_lookup: Optional[Callable]) -> Decimal
- list_transactions(...) -> List[Transaction]
- get_transaction(transaction_id) -> Transaction
- to_dict() and from_dict() for serialization (optional)

All operations record Transaction entries (deposit/withdraw/buy/sell) in chronological order with a generated id and timestamp.

---

## Data model

Transaction dataclass fields:

- id: str — unique transaction id (uuid4 hex)
- type: str — one of "deposit", "withdraw", "buy", "sell"
- amount: Decimal — cash amount for deposit/withdraw; for buy/sell should be total transaction cash flow (positive for deposits/sells, negative for withdrawals/buys) or use explicit sign convention described below
- symbol: Optional[str] — present for buy/sell transactions
- quantity: Optional[int] — present for buy/sell
- price_per_share: Optional[Decimal] — for buy/sell, price used at the time of transaction
- total: Decimal — computed total for buy/sell = quantity * price_per_share (quantized to cents)
- timestamp: datetime — UTC timezone-aware
- note: Optional[str] — freeform note
- resulting_cash_balance: Decimal — cash balance after this transaction (for easy inspection)
- resulting_holdings_snapshot: Optional[Dict[str, int]] — optional snapshot of holdings after transaction (can be a shallow copy)

Transaction semantics:
- For deposit: type="deposit", amount == total == positive value
- For withdraw: type="withdraw", amount == total == positive value; cash is reduced by total
- For buy: type="buy", price_per_share set, quantity positive int; total = quantity * price_per_share; cash reduced by total (amount may be recorded as positive for accounting but note in doc that buy reduces cash)
- For sell: type="sell", similar but cash increases

Quantization: All monetary values are Decimal and quantized to Decimal("0.01").

---

## Exceptions

- class AccountError(Exception): base class for account related errors
- class InsufficientFundsError(AccountError): raised when withdraw or buy would make cash < 0
- class InsufficientSharesError(AccountError): raised when attempting to sell more shares than held
- class InvalidTransactionError(AccountError): raised when inputs are invalid (negative amounts, zero quantity, invalid symbol etc.)

---

## External price lookup

Default price oracle function provided in module:

Signature:
```python
def get_share_price(symbol: str) -> Decimal
```

Test implementation returns fixed Decimal prices (quantized to cents):

- "AAPL" -> Decimal("150.00")
- "TSLA" -> Decimal("700.00")
- "GOOGL" -> Decimal("2700.00")
- Raises KeyError or InvalidTransactionError for unknown symbols (implementation choice; design suggests raising InvalidTransactionError)

The Account methods that need prices accept an optional price_lookup parameter of type Callable[[str], Decimal]. If None, the module-level get_share_price is used. This allows tests to inject mocks.

---

## Account class API

Class name: Account

Constructor:
```python
class Account:
    def __init__(
        self,
        user_id: str,
        initial_deposit: Decimal = Decimal("0.00"),
        currency: str = "USD",
        timestamp: Optional[datetime] = None,
        lock: Optional[threading.Lock] = None
    ) -> None:
        ...
```

Behavior:
- user_id: unique id for the account
- initial_deposit: if provided > 0, a deposit transaction is recorded at creation time
- currency: e.g. "USD"
- timestamp: optional timestamp for the creation deposit; if None, use datetime.now(timezone.utc)
- lock: optional threading.Lock passed in, otherwise create internal Lock if thread-safety desired

Stored state (suggested private attributes):
- self.user_id: str
- self.currency: str
- self._cash: Decimal — cash balance
- self._holdings: Dict[str, int] — mapping symbol -> integer shares
- self._ledger: List[Transaction] — chronological list of transactions
- self._initial_deposit: Decimal — record the initial deposit amount (only the creation initial deposit)
- self._total_deposits: Decimal — sum of all deposit amounts (including initial)
- self._total_withdrawals: Decimal
- self._lock: threading.Lock

Public methods (signatures, detailed behavior):

1) deposit
```python
def deposit(self, amount: Decimal, timestamp: Optional[datetime]=None, note: Optional[str]=None) -> "Transaction":
    """
    Add cash to the account. Records a deposit transaction.

    Raises:
      InvalidTransactionError if amount <= 0
    Returns:
      Transaction created and appended to ledger
    """
```

- Validate amount > 0
- Update _cash, _total_deposits
- Create Transaction with resulting_cash_balance and optional holdings snapshot

2) withdraw
```python
def withdraw(self, amount: Decimal, timestamp: Optional[datetime]=None, note: Optional[str]=None) -> "Transaction":
    """
    Remove cash from account. Prevents negative cash balance.

    Raises:
      InvalidTransactionError if amount <= 0
      InsufficientFundsError if amount > available cash
    Returns:
      Transaction recorded
    """
```

- Validate amount > 0
- Check self._cash >= amount, else raise InsufficientFundsError
- Subtract from _cash, update _total_withdrawals
- Record Transaction

3) buy
```python
def buy(self, symbol: str, quantity: int, price_lookup: Optional[Callable[[str], Decimal]]=None, timestamp: Optional[datetime]=None, note: Optional[str]=None) -> "Transaction":
    """
    Buy `quantity` shares of `symbol` at the current price from price_lookup or default get_share_price.
    Prevent buying if cash insufficient.

    Raises:
      InvalidTransactionError if quantity <= 0 or symbol invalid
      InsufficientFundsError if cash < quantity * price
    Returns:
      Transaction recorded
    """
```

- Normalize symbol (uppercase, strip)
- Validate quantity is positive int
- Resolve price_lookup -> price_per_share (Decimal)
- Compute total_cost = (price_per_share * quantity).quantize(Decimal("0.01"))
- Check self._cash >= total_cost else raise InsufficientFundsError
- Deduct from _cash, add to holdings (atomic under lock)
- Record Transaction (type "buy", amount maybe stored as total_cost)

4) sell
```python
def sell(self, symbol: str, quantity: int, price_lookup: Optional[Callable[[str], Decimal]]=None, timestamp: Optional[datetime]=None, note: Optional[str]=None) -> "Transaction":
    """
    Sell `quantity` shares of `symbol` at the current price.
    Prevent selling more than held.

    Raises:
      InvalidTransactionError if invalid inputs
      InsufficientSharesError if quantity > holdings for symbol
    Returns:
      Transaction recorded
    """
```

- Validate inputs
- Check holdings >= quantity
- Resolve price_per_share
- Compute total_proceeds = (price_per_share * quantity).quantize(Decimal("0.01"))
- Reduce holdings; if holdings drop to 0, optionally remove key
- Add to _cash
- Record Transaction

5) get_holdings
```python
def get_holdings(self) -> Dict[str, int]:
    """
    Return a shallow copy of holdings mapping symbol -> quantity
    """
```

6) get_cash_balance
```python
def get_cash_balance(self) -> Decimal:
    """
    Return current cash balance (quantized).
    """
```

7) get_portfolio_value
```python
def get_portfolio_value(self, price_lookup: Optional[Callable[[str], Decimal]]=None) -> Decimal:
    """
    Compute market value of all holdings using price_lookup (or default).
    Returns quantized Decimal.
    """
```

- For each symbol in holdings, multiply its quantity by current price_per_share
- If price_lookup raises for unknown symbol, propagate or treat missing price as zero (design choice: raise InvalidTransactionError to surface missing price)

8) get_total_equity
```python
def get_total_equity(self, price_lookup: Optional[Callable[[str], Decimal]]=None) -> Decimal:
    """
    Return cash_balance + portfolio_value.
    """
```

9) get_profit_loss_from_initial
```python
def get_profit_loss_from_initial(self, price_lookup: Optional[Callable[[str], Decimal]]=None) -> Decimal:
    """
    Profit (positive) or loss (negative) relative to the initial deposit amount only.
    Calculated as: total_equity - self._initial_deposit

    Note: If no initial_deposit was provided at account creation, initial_deposit == 0.
    """
```

10) get_profit_loss_from_net_deposits
```python
def get_profit_loss_from_net_deposits(self, price_lookup: Optional[Callable[[str], Decimal]]=None) -> Decimal:
    """
    Profit or loss relative to net deposited capital.
    Net_deposited = total_deposits - total_withdrawals
    Returns: total_equity - net_deposited
    """
```

11) list_transactions
```python
def list_transactions(self, start_time: Optional[datetime]=None, end_time: Optional[datetime]=None, types: Optional[List[str]]=None) -> List["Transaction"]:
    """
    Return transactions in chronological order filtered by optional time range and transaction types.
    """
```

- start_time and end_time are inclusive; if None, no bound
- types: e.g. ["buy", "sell", "deposit"]

12) get_transaction
```python
def get_transaction(self, transaction_id: str) -> "Transaction":
    """
    Return transaction with given id or raise KeyError/InvalidTransactionError if not found.
    """
```

13) to_dict / from_dict (optional)
```python
def to_dict(self) -> Dict[str, Any]:
    """
    Return a serializable dict that contains current account state (cash, holdings, ledger)
    """
```

```python
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "Account":
    """
    Create an Account instance from a dict produced by to_dict.
    """
```

---

## Private helper method signatures

These methods are implementation details but provided here to guide build:

1) _now()
```python
def _now(self) -> datetime:
    """Return timezone-aware UTC now (datetime.now(timezone.utc))"""
```

2) _record_transaction
```python
def _record_transaction(self, ttype: str, amount: Decimal, timestamp: datetime, symbol: Optional[str], quantity: Optional[int], price_per_share: Optional[Decimal], note: Optional[str]) -> "Transaction":
    """
    Create Transaction object, append to ledger, and return it.
    Populates resulting_cash_balance, possibly snapshot holdings.
    """
```

3) _validate_amount
```python
def _validate_amount(self, amount: Decimal) -> None:
    """Raise InvalidTransactionError if amount <= 0 or not Decimal"""
```

4) _validate_quantity
```python
def _validate_quantity(self, quantity: int) -> None:
    """Raise InvalidTransactionError if quantity <= 0 or not int"""
```

5) _quantize_currency
```python
def _quantize_currency(self, amount: Decimal) -> Decimal:
    """Return amount quantized to Decimal('0.01') with HALF_UP"""
```

---

## Usage example (pseudo-code illustrating intended API)

This is not code to include verbatim, but demonstrates how the API should be used.

```python
from decimal import Decimal
from accounts import Account, get_share_price

acct = Account(user_id="user123", initial_deposit=Decimal("10000.00"))
acct.deposit(Decimal("2000.00"))
acct.buy("AAPL", 10)  # uses default get_share_price -> cost 150 * 10 = 1500
acct.sell("AAPL", 2)
print(acct.get_cash_balance())
print(acct.get_holdings())  # {"AAPL": 8}
print(acct.get_portfolio_value())  # 8 * 150 = 1200
print(acct.get_total_equity())  # cash + portfolio
print(acct.get_profit_loss_from_initial())  # equity - 10000.00
for t in acct.list_transactions():
    print(t)
```

---

## Edge cases and decisions (explicit)

- Monetary arithmetic: use Decimal to avoid float rounding. Quantize all stored currency values to cents (Decimal('0.01')).
- Fractional shares: The design requires integer quantities for shares (no fractional share support). If fractional shares are desired, change type of quantity to Decimal and validate accordingly.
- Unknown symbols: The default get_share_price only supports AAPL, TSLA, GOOGL in the test implementation. If a price is unknown, Account methods should raise InvalidTransactionError (so calling code knows the price is unavailable). Alternatively, allow price_lookup injection that returns 0 for missing prices — but the built-in behavior is to error.
- Profit definition: Two methods are provided:
  - get_profit_loss_from_initial(): profit relative to initial_deposit only.
  - get_profit_loss_from_net_deposits(): profit relative to net capital injected across the account's lifetime (sum of deposits minus withdrawals).
- Ordering: ledger is append-only, chronological. list_transactions returns a copy or slices to avoid external mutation.
- Concurrency: Account uses a Lock to protect concurrent modifications of _cash, _holdings, and _ledger. Every public mutating method should acquire the lock at start and release at end (context manager recommended).
- Transaction result snapshot: For convenience, Transaction includes resulting_cash_balance and optionally snapshot of holdings after the transaction.
- Persistence: This spec describes in-memory structure. Persistence or DB writing is outside scope, but to_dict/from_dict provide hooks for serialization.

---

## Default test price oracle (function signature and behavior)

Signature to include in module:
```python
def get_share_price(symbol: str) -> Decimal:
    """
    Test implementation of a price oracle. Returns Decimal price for supported symbols:

      AAPL -> Decimal('150.00')
      TSLA -> Decimal('700.00')
      GOOGL -> Decimal('2700.00')

    Raises InvalidTransactionError for unsupported symbols.
    """
```

---

## Full method and function signature list (as a single block for quick reference)

```python
# Module-level
def get_share_price(symbol: str) -> Decimal

# Exceptions
class AccountError(Exception)
class InsufficientFundsError(AccountError)
class InsufficientSharesError(AccountError)
class InvalidTransactionError(AccountError)

# Transaction dataclass (example fields)
@dataclass
class Transaction:
    id: str
    type: str  # "deposit"/"withdraw"/"buy"/"sell"
    amount: Decimal
    symbol: Optional[str]
    quantity: Optional[int]
    price_per_share: Optional[Decimal]
    total: Decimal
    timestamp: datetime
    note: Optional[str]
    resulting_cash_balance: Decimal
    resulting_holdings_snapshot: Optional[Dict[str, int]]

# Primary class
class Account:
    def __init__(self, user_id: str, initial_deposit: Decimal = Decimal("0.00"), currency: str = "USD", timestamp: Optional[datetime] = None, lock: Optional[threading.Lock] = None) -> None

    def deposit(self, amount: Decimal, timestamp: Optional[datetime]=None, note: Optional[str]=None) -> Transaction

    def withdraw(self, amount: Decimal, timestamp: Optional[datetime]=None, note: Optional[str]=None) -> Transaction

    def buy(self, symbol: str, quantity: int, price_lookup: Optional[Callable[[str], Decimal]]=None, timestamp: Optional[datetime]=None, note: Optional[str]=None) -> Transaction

    def sell(self, symbol: str, quantity: int, price_lookup: Optional[Callable[[str], Decimal]]=None, timestamp: Optional[datetime]=None, note: Optional[str]=None) -> Transaction

    def get_holdings(self) -> Dict[str, int]

    def get_cash_balance(self) -> Decimal

    def get_portfolio_value(self, price_lookup: Optional[Callable[[str], Decimal]]=None) -> Decimal

    def get_total_equity(self, price_lookup: Optional[Callable[[str], Decimal]]=None) -> Decimal

    def get_profit_loss_from_initial(self, price_lookup: Optional[Callable[[str], Decimal]]=None) -> Decimal

    def get_profit_loss_from_net_deposits(self, price_lookup: Optional[Callable[[str], Decimal]]=None) -> Decimal

    def list_transactions(self, start_time: Optional[datetime]=None, end_time: Optional[datetime]=None, types: Optional[List[str]]=None) -> List[Transaction]

    def get_transaction(self, transaction_id: str) -> Transaction

    def to_dict(self) -> Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Account"
```

---

## Testing guidance

- Unit tests should:
  - Create account with initial deposit, assert ledger has one deposit transaction and cash balance equals deposit.
  - Test deposit/withdraw flows with correct ledger entries and balances.
  - Test buy with sufficient funds reduces cash and increases holdings; ledger records price used and resulting balance.
  - Test buy with insufficient funds raises InsufficientFundsError and that state is unchanged.
  - Test sell reduces holdings and increases cash; selling more than held raises InsufficientSharesError.
  - Test portfolio value and equity with injected price_lookup that returns deterministic values.
  - Test profit/loss computations for both initial deposit and net deposits in different scenarios (multiple deposits and withdrawals).
  - Test transaction filtering by date range and type.
  - Test thread-safety with concurrent buys/sells if you implement Lock usage; verify invariants hold.

---

## Implementation notes and suggestions

- Use Decimal for monetary arithmetic. Example quantization function:
  - quantize(amount) -> amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
- Use uuid.uuid4().hex to create transaction ids.
- Use datetime.now(timezone.utc) for timestamps.
- Keep ledger append-only and never expose direct references to internal ledger list or holdings mapping (always return copies).
- Document the behavior of profit/loss choice explicitly in module-level docstring (to avoid confusion about "initial deposit" vs net deposits).
- Provide clear docstrings for each method and type hints for static checking.
- Avoid side-effects in price lookup: price_lookup should be a pure function returning Decimal.

---

This design describes everything needed to implement a complete, testable, single-file accounts.py module exposing an Account class with the required behavior: create account, deposit, withdraw, buy, sell, portfolio valuation, profit/loss reporting, transaction listing, and enforced constraints for funds and holdings. The included get_share_price provides a simple deterministic oracle for tests (AAPL/TSLA/GOOGL).