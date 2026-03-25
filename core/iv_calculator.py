# core/iv_calculator.py
"""Implied Volatility Calculator using Black-Scholes model.

This module provides an IV calculator using the Newton-Raphson iteration method
for computing implied volatility from option prices.
"""
import math
from typing import List, Optional, Tuple

from core.models import CallOrPut, OptionQuote


class IVCalculator:
    """Implied Volatility Calculator using Black-Scholes model.

    Uses Newton-Raphson iteration to find implied volatility.

    Attributes:
        risk_free_rate: Risk-free interest rate (default: 0.03)
        max_iterations: Maximum iterations for Newton-Raphson (default: 100)
        tolerance: Convergence tolerance (default: 1e-6)
        iv_min: Minimum IV bound (default: 0.001)
        iv_max: Maximum IV bound (default: 5.0)
    """

    def __init__(
        self,
        risk_free_rate: float = 0.03,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ):
        """Initialize IV calculator.

        Args:
            risk_free_rate: Annual risk-free interest rate
            max_iterations: Maximum Newton-Raphson iterations
            tolerance: Convergence tolerance for IV calculation
        """
        self.risk_free_rate = risk_free_rate
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.iv_min = 0.001
        self.iv_max = 5.0

    def _norm_cdf(self, x: float) -> float:
        """Calculate cumulative distribution function for standard normal.

        Uses math.erf for approximation: CDF(x) = 0.5 * (1 + erf(x / sqrt(2)))

        Args:
            x: Input value

        Returns:
            Cumulative probability
        """
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _norm_pdf(self, x: float) -> float:
        """Calculate probability density function for standard normal.

        Args:
            x: Input value

        Returns:
            Probability density
        """
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    def _bs_price(
        self,
        S: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        option_type: CallOrPut
    ) -> float:
        """Calculate Black-Scholes option price.

        Args:
            S: Underlying asset price (future price)
            K: Strike price
            r: Risk-free interest rate
            sigma: Volatility
            T: Time to expiry in years
            option_type: CALL or PUT

        Returns:
            Theoretical option price
        """
        if T <= 0 or S <= 0 or K <= 0 or sigma <= 0:
            # For expired options or invalid inputs, return intrinsic value
            if option_type == CallOrPut.CALL:
                return max(0.0, S - K)
            else:
                return max(0.0, K - S)

        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        discount = math.exp(-r * T)

        if option_type == CallOrPut.CALL:
            price = S * self._norm_cdf(d1) - K * discount * self._norm_cdf(d2)
        else:
            price = K * discount * self._norm_cdf(-d2) - S * self._norm_cdf(-d1)

        return price

    def _bs_vega(
        self,
        S: float,
        K: float,
        r: float,
        sigma: float,
        T: float
    ) -> float:
        """Calculate Black-Scholes Vega (sensitivity to volatility).

        Args:
            S: Underlying asset price
            K: Strike price
            r: Risk-free interest rate
            sigma: Volatility
            T: Time to expiry in years

        Returns:
            Vega value
        """
        if T <= 0 or S <= 0 or K <= 0 or sigma <= 0:
            return 0.0

        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)

        return S * self._norm_pdf(d1) * sqrt_T

    def calculate_iv(
        self,
        option: OptionQuote,
        future_price: float,
        time_to_expiry: Optional[float] = None
    ) -> Optional[float]:
        """Calculate implied volatility for an option.

        Uses Newton-Raphson iteration to find the IV that makes the
        Black-Scholes price equal to the market price.

        Args:
            option: OptionQuote object with strike, type, and price
            future_price: Current price of the underlying future
            time_to_expiry: Time to expiry in years. If None, uses option's expiry_date

        Returns:
            Implied volatility as decimal (e.g., 0.25 for 25%), or None if calculation fails

        Raises:
            ValueError: If future_price <= 0 or option.last_price <= 0
        """
        # Input validation
        if future_price <= 0:
            raise ValueError(f"Future price must be positive, got {future_price}")
        if option.last_price <= 0:
            raise ValueError(f"Option price must be positive, got {option.last_price}")

        # Handle time to expiry
        if time_to_expiry is None:
            time_to_expiry = option.time_to_expiry()

        T = time_to_expiry

        # Edge case: expired option
        if T <= 0:
            return None

        K = option.strike_price
        S = future_price
        r = self.risk_free_rate
        market_price = option.last_price

        # Calculate intrinsic value
        if option.call_or_put == CallOrPut.CALL:
            intrinsic = max(0.0, S - K)
        else:
            intrinsic = max(0.0, K - S)

        # Deep ITM option: market price close to intrinsic
        if market_price <= intrinsic + 1e-10:
            # No time value, return minimum IV
            return self.iv_min

        # Deep OTM option check
        if option.call_or_put == CallOrPut.CALL:
            # Deep OTM call: S << K
            if S < K * 0.5:
                # Price should be very small
                if market_price < 1e-10:
                    return None
        else:
            # Deep OTM put: S >> K
            if S > K * 2.0:
                if market_price < 1e-10:
                    return None

        # Newton-Raphson iteration
        iv = 0.2  # Starting guess

        for _ in range(self.max_iterations):
            # Calculate price and vega at current iv
            price = self._bs_price(S, K, r, iv, T, option.call_or_put)
            vega = self._bs_vega(S, K, r, iv, T)

            # Avoid division by zero
            if abs(vega) < 1e-10:
                break

            # Newton-Raphson update
            diff = market_price - price
            iv_new = iv + diff / vega

            # Apply bounds
            iv_new = max(self.iv_min, min(self.iv_max, iv_new))

            # Check convergence
            if abs(iv_new - iv) < self.tolerance:
                return iv_new

            iv = iv_new

        # If we didn't converge, check if we're close enough
        final_price = self._bs_price(S, K, r, iv, T, option.call_or_put)
        if abs(final_price - market_price) / market_price < 0.01:  # 1% relative error
            return iv

        return None

    def _calculate_time_to_expiry(self, expiry_date) -> float:
        """Calculate time to expiry in years from expiry date.

        Args:
            expiry_date: Expiration date (datetime object or string)

        Returns:
            Time to expiry in years
        """
        from datetime import datetime

        if isinstance(expiry_date, str):
            # Try to parse string date
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y%m%d']:
                try:
                    expiry_date = datetime.strptime(expiry_date, fmt)
                    break
                except ValueError:
                    continue

        if isinstance(expiry_date, datetime):
            now = datetime.now()
            if expiry_date <= now:
                return 0.0
            days = (expiry_date - now).days
            return days / 365.0

        raise ValueError(f"Cannot parse expiry_date: {expiry_date}")

    def calculate_smile(
        self,
        options: List[OptionQuote],
        future_price: float,
        time_to_expiry: Optional[float] = None
    ) -> List[Tuple[float, Optional[float]]]:
        """Calculate volatility smile for a list of options.

        Args:
            options: List of OptionQuote objects
            future_price: Current price of the underlying future
            time_to_expiry: Time to expiry in years (optional, uses option's expiry_date)

        Returns:
            List of (strike_price, implied_volatility) tuples
            IV is None if calculation failed for that option
        """
        smile = []
        for option in options:
            try:
                iv = self.calculate_iv(option, future_price, time_to_expiry)
                smile.append((option.strike_price, iv))
            except ValueError:
                smile.append((option.strike_price, None))

        return smile

    def calculate_greeks(
        self,
        option: OptionQuote,
        future_price: float,
        iv: float,
        time_to_expiry: Optional[float] = None
    ) -> dict:
        """Calculate option Greeks.

        Args:
            option: OptionQuote object
            future_price: Current price of the underlying future
            iv: Implied volatility
            time_to_expiry: Time to expiry in years

        Returns:
            Dictionary with delta, gamma, vega, theta, rho
        """
        if time_to_expiry is None:
            time_to_expiry = option.time_to_expiry()

        T = time_to_expiry
        K = option.strike_price
        S = future_price
        r = self.risk_free_rate
        sigma = iv

        if T <= 0 or S <= 0 or K <= 0 or sigma <= 0:
            return {"delta": None, "gamma": None, "vega": None, "theta": None, "rho": None}

        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        # Delta
        if option.call_or_put == CallOrPut.CALL:
            delta = self._norm_cdf(d1)
        else:
            delta = self._norm_cdf(d1) - 1.0

        # Gamma (same for call and put)
        gamma = self._norm_pdf(d1) / (S * sigma * sqrt_T)

        # Vega (same for call and put)
        vega = S * self._norm_pdf(d1) * sqrt_T

        # Theta
        discount = math.exp(-r * T)
        if option.call_or_put == CallOrPut.CALL:
            theta = (-S * self._norm_pdf(d1) * sigma / (2 * sqrt_T)
                     - r * K * discount * self._norm_cdf(d2))
        else:
            theta = (-S * self._norm_pdf(d1) * sigma / (2 * sqrt_T)
                     + r * K * discount * self._norm_cdf(-d2))

        # Rho
        if option.call_or_put == CallOrPut.CALL:
            rho = K * T * discount * self._norm_cdf(d2)
        else:
            rho = -K * T * discount * self._norm_cdf(-d2)

        return {
            "delta": delta,
            "gamma": gamma,
            "vega": vega,
            "theta": theta / 365.0,  # Per day
            "rho": rho / 100.0  # Per 1% rate change
        }