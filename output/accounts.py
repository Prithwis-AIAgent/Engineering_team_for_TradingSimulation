from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Optional, Callable, Dict, List, Any
import uuid
import threading

# Set Decimal precision
getcontext().prec = 28

# Exceptions
class AccountError(Exception):
    """Base class for account-related errors."""

class InsufficientFundsError(AccountError):
    """Raised when an operation would result in negative cash balance."""

class InsufficientSharesError(AccountError):
    """Raised when attempting to sell more shares than are held."""

class InvalidTransactionError(AccountError):
    """Raised when transaction inputs are invalid or unsupported symbols are used."""

# Helper for currency quantization
_CURRENCY_QUANT = Decimal("0.01")

def _quantize_currency(amount: Decimal) -> Decimal:
    if not isinstance(amount, Decimal):
        raise InvalidTransactionError("Amount must be a Decimal")
    return amount.quantize(_CURRENCY_QUANT, rounding=ROUND_HALF_UP)

# Simple price oracle for tests
def get_share_price(symbol: str) -> Decimal:
    """Test implementation of a price oracle. Supported symbols:

    AAPL -> 150.00
    TSLA -> 700.00
    GOOGL -> 2700.00

    Raises InvalidTransactionError for unsupported symbols.
    """
    if not symbol or not isinstance(symbol, str):
        raise InvalidTransactionError("Invalid symbol")
    s = symbol.strip().upper()
    prices = {
        "AAPL": Decimal("150.00"),
        "TSLA": Decimal("700.00"),
        "GOOGL": Decimal("2700.00"),
    }
    if s not in prices:
        raise InvalidTransactionError(f"Price for symbol '{symbol}' is not available")
    return _quantize_currency(prices[s])

@dataclass
class Transaction:
    id: str
    type: str  # "deposit"/"withdraw"/"buy"/"sell"
    amount: Decimal  # positive amount (for deposits/withdrawals); for buy/sell positive total
    symbol: Optional[str]
    quantity: Optional[int]
    price_per_share: Optional[Decimal]
    total: Decimal
    timestamp: datetime
    note: Optional[str]
    resulting_cash_balance: Decimal
    resulting_holdings_snapshot: Optional[Dict[str, int]] = field(default=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "amount": str(self.amount),
            "symbol": self.symbol,
            "quantity": self.quantity,
            "price_per_share": (str(self.price_per_share) if self.price_per_share is not None else None),
            "total": str(self.total),
            "timestamp": self.timestamp.isoformat(),
            "note": self.note,
            "resulting_cash_balance": str(self.resulting_cash_balance),
            "resulting_holdings_snapshot": dict(self.resulting_holdings_snapshot) if self.resulting_holdings_snapshot is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        ts = data.get("timestamp")
        timestamp = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
        price = Decimal(data["price_per_share"]) if data.get("price_per_share") is not None else None
        return cls(
            id=data["id"],
            type=data["type"],
            amount=Decimal(data["amount"]),
            symbol=data.get("symbol"),
            quantity=data.get("quantity"),
            price_per_share=price,
            total=Decimal(data["total"]),
            timestamp=timestamp,
            note=data.get("note"),
            resulting_cash_balance=Decimal(data["resulting_cash_balance"]),
            resulting_holdings_snapshot=data.get("resulting_holdings_snapshot"),
        )

class Account:
    def __init__(
        self,
        user_id: str,
        initial_deposit: Decimal = Decimal("0.00"),
        currency: str = "USD",
        timestamp: Optional[datetime] = None,
        lock: Optional[threading.Lock] = None,
    ) -> None:
        if not user_id or not isinstance(user_id, str):
            raise InvalidTransactionError("user_id must be a non-empty string")
        self.user_id = user_id
        self.currency = currency
        self._cash = _quantize_currency(Decimal("0.00"))
        self._holdings: Dict[str, int] = {}
        self._ledger: List[Transaction] = []
        self._initial_deposit = _quantize_currency(initial_deposit) if initial_deposit is not None else Decimal("0.00")
        self._total_deposits = Decimal("0.00")
        self._total_withdrawals = Decimal("0.00")
        self._lock = lock if lock is not None else threading.Lock()

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        if self._initial_deposit and self._initial_deposit > Decimal("0.00"):
            # Record initial deposit
            self._cash = _quantize_currency(self._initial_deposit)
            self._total_deposits = _quantize_currency(self._initial_deposit)
            tx = self._record_transaction(
                ttype="deposit",
                amount=self._initial_deposit,
                timestamp=timestamp,
                symbol=None,
                quantity=None,
                price_per_share=None,
                note="initial_deposit",
            )

    # Private helpers
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _validate_amount(self, amount: Decimal) -> None:
        if not isinstance(amount, Decimal):
            raise InvalidTransactionError("Amount must be a Decimal")
        if amount <= Decimal("0.00"):
            raise InvalidTransactionError("Amount must be greater than zero")

    def _validate_quantity(self, quantity: int) -> None:
        if not isinstance(quantity, int):
            raise InvalidTransactionError("Quantity must be an integer")
        if quantity <= 0:
            raise InvalidTransactionError("Quantity must be greater than zero")

    def _record_transaction(
        self,
        ttype: str,
        amount: Decimal,
        timestamp: datetime,
        symbol: Optional[str],
        quantity: Optional[int],
        price_per_share: Optional[Decimal],
        note: Optional[str],
    ) -> Transaction:
        # Ensure currency quantization
        amount_q = _quantize_currency(amount)
        price_q = _quantize_currency(price_per_share) if price_per_share is not None else None
        total = _quantize_currency(price_q * quantity) if (price_q is not None and quantity is not None) else amount_q
        tx = Transaction(
            id=uuid.uuid4().hex,
            type=ttype,
            amount=amount_q,
            symbol=symbol,
            quantity=quantity,
            price_per_share=price_q,
            total=total,
            timestamp=timestamp,
            note=note,
            resulting_cash_balance=_quantize_currency(self._cash),
            resulting_holdings_snapshot=dict(self._holdings) if self._holdings else None,
        )
        self._ledger.append(tx)
        return tx

    # Public API
    def deposit(self, amount: Decimal, timestamp: Optional[datetime] = None, note: Optional[str] = None) -> Transaction:
        """Add cash to the account. Records a deposit transaction."""
        if timestamp is None:
            timestamp = self._now()
        self._validate_amount(amount)
        with self._lock:
            self._cash = _quantize_currency(self._cash + amount)
            self._total_deposits = _quantize_currency(self._total_deposits + amount)
            return self._record_transaction(
                ttype="deposit",
                amount=amount,
                timestamp=timestamp,
                symbol=None,
                quantity=None,
                price_per_share=None,
                note=note,
            )

    def withdraw(self, amount: Decimal, timestamp: Optional[datetime] = None, note: Optional[str] = None) -> Transaction:
        """Remove cash from account. Prevents negative cash balance."""
        if timestamp is None:
            timestamp = self._now()
        self._validate_amount(amount)
        with self._lock:
            if self._cash < amount:
                raise InsufficientFundsError("Insufficient cash to withdraw the requested amount")
            self._cash = _quantize_currency(self._cash - amount)
            self._total_withdrawals = _quantize_currency(self._total_withdrawals + amount)
            return self._record_transaction(
                ttype="withdraw",
                amount=amount,
                timestamp=timestamp,
                symbol=None,
                quantity=None,
                price_per_share=None,
                note=note,
            )

    def buy(
        self,
        symbol: str,
        quantity: int,
        price_lookup: Optional[Callable[[str], Decimal]] = None,
        timestamp: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        """Buy `quantity` shares of `symbol` at current price from price_lookup or default.
        Raises InsufficientFundsError if cash insufficient.
        """
        if timestamp is None:
            timestamp = self._now()
        if not symbol or not isinstance(symbol, str):
            raise InvalidTransactionError("Symbol must be a non-empty string")
        self._validate_quantity(quantity)
        price_fn = price_lookup if price_lookup is not None else get_share_price
        symbol_norm = symbol.strip().upper()
        price = price_fn(symbol_norm)
        if not isinstance(price, Decimal):
            raise InvalidTransactionError("Price lookup must return a Decimal")
        price_q = _quantize_currency(price)
        total_cost = _quantize_currency(price_q * quantity)
        with self._lock:
            if self._cash < total_cost:
                raise InsufficientFundsError("Insufficient cash to complete purchase")
            # Deduct cash and add holdings
            self._cash = _quantize_currency(self._cash - total_cost)
            self._holdings[symbol_norm] = self._holdings.get(symbol_norm, 0) + quantity
            return self._record_transaction(
                ttype="buy",
                amount=total_cost,
                timestamp=timestamp,
                symbol=symbol_norm,
                quantity=quantity,
                price_per_share=price_q,
                note=note,
            )

    def sell(
        self,
        symbol: str,
        quantity: int,
        price_lookup: Optional[Callable[[str], Decimal]] = None,
        timestamp: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        """Sell `quantity` shares of `symbol` at current price. Prevents selling more than held."""
        if timestamp is None:
            timestamp = self._now()
        if not symbol or not isinstance(symbol, str):
            raise InvalidTransactionError("Symbol must be a non-empty string")
        self._validate_quantity(quantity)
        symbol_norm = symbol.strip().upper()
        with self._lock:
            held = self._holdings.get(symbol_norm, 0)
            if held < quantity:
                raise InsufficientSharesError(f"Attempting to sell {quantity} shares but only {held} held for {symbol_norm}")
            price_fn = price_lookup if price_lookup is not None else get_share_price
            price = price_fn(symbol_norm)
            if not isinstance(price, Decimal):
                raise InvalidTransactionError("Price lookup must return a Decimal")
            price_q = _quantize_currency(price)
            total_proceeds = _quantize_currency(price_q * quantity)
            # Update holdings and cash
            remaining = held - quantity
            if remaining:
                self._holdings[symbol_norm] = remaining
            else:
                # remove zero holdings
                self._holdings.pop(symbol_norm, None)
            self._cash = _quantize_currency(self._cash + total_proceeds)
            return self._record_transaction(
                ttype="sell",
                amount=total_proceeds,
                timestamp=timestamp,
                symbol=symbol_norm,
                quantity=quantity,
                price_per_share=price_q,
                note=note,
            )

    def get_holdings(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._holdings)

    def get_cash_balance(self) -> Decimal:
        with self._lock:
            return _quantize_currency(self._cash)

    def get_portfolio_value(self, price_lookup: Optional[Callable[[str], Decimal]] = None) -> Decimal:
        price_fn = price_lookup if price_lookup is not None else get_share_price
        total = Decimal("0.00")
        with self._lock:
            for symbol, qty in self._holdings.items():
                price = price_fn(symbol)
                if not isinstance(price, Decimal):
                    raise InvalidTransactionError("Price lookup must return a Decimal")
                price_q = _quantize_currency(price)
                total += _quantize_currency(price_q * qty)
        return _quantize_currency(total)

    def get_total_equity(self, price_lookup: Optional[Callable[[str], Decimal]] = None) -> Decimal:
        cash = self.get_cash_balance()
        portfolio = self.get_portfolio_value(price_lookup=price_lookup)
        return _quantize_currency(cash + portfolio)

    def get_profit_loss_from_initial(self, price_lookup: Optional[Callable[[str], Decimal]] = None) -> Decimal:
        equity = self.get_total_equity(price_lookup=price_lookup)
        return _quantize_currency(equity - _quantize_currency(self._initial_deposit))

    def get_profit_loss_from_net_deposits(self, price_lookup: Optional[Callable[[str], Decimal]] = None) -> Decimal:
        equity = self.get_total_equity(price_lookup=price_lookup)
        net_deposited = _quantize_currency(self._total_deposits - self._total_withdrawals)
        return _quantize_currency(equity - net_deposited)

    def list_transactions(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        types: Optional[List[str]] = None,
    ) -> List[Transaction]:
        with self._lock:
            result: List[Transaction] = []
            for tx in self._ledger:
                if start_time is not None and tx.timestamp < start_time:
                    continue
                if end_time is not None and tx.timestamp > end_time:
                    continue
                if types is not None and tx.type not in types:
                    continue
                result.append(tx)
            return list(result)

    def get_transaction(self, transaction_id: str) -> Transaction:
        with self._lock:
            for tx in self._ledger:
                if tx.id == transaction_id:
                    return tx
        raise InvalidTransactionError(f"Transaction with id {transaction_id} not found")

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "user_id": self.user_id,
                "currency": self.currency,
                "cash": str(self._cash),
                "holdings": dict(self._holdings),
                "initial_deposit": str(self._initial_deposit),
                "total_deposits": str(self._total_deposits),
                "total_withdrawals": str(self._total_withdrawals),
                "ledger": [tx.to_dict() for tx in self._ledger],
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Account":
        user_id = data["user_id"]
        initial_deposit = Decimal(data.get("initial_deposit", "0.00"))
        currency = data.get("currency", "USD")
        acct = cls(user_id=user_id, initial_deposit=Decimal("0.00"), currency=currency)
        # Overwrite internals according to provided data
        with acct._lock:
            acct._cash = _quantize_currency(Decimal(data.get("cash", "0.00")))
            acct._holdings = dict(data.get("holdings", {}))
            acct._initial_deposit = _quantize_currency(initial_deposit)
            acct._total_deposits = _quantize_currency(Decimal(data.get("total_deposits", "0.00")))
            acct._total_withdrawals = _quantize_currency(Decimal(data.get("total_withdrawals", "0.00")))
            # Rebuild ledger
            acct._ledger = [Transaction.from_dict(d) for d in data.get("ledger", [])]
        return acct