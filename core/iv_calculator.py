# core/iv_calculator.py
"""Implied Volatility Calculator using Black-Scholes model.

This module provides an IV calculator using the Newton-Raphson iteration method
for computing implied volatility from option prices.

Features:
- Black-Scholes option pricing
- Implied volatility calculation (Newton-Raphson + bisection fallback)
- Greeks calculation (Delta, Gamma, Vega, Theta, Rho)
- Volatility smile analysis
- Vectorized operations using NumPy
"""
import math
from typing import List, Optional, Tuple, Union
from datetime import datetime

import numpy as np
from scipy import stats

from core.models import CallOrPut, OptionQuote


class IVCalculator:
    """Implied Volatility Calculator using Black-Scholes model.

    Uses Newton-Raphson iteration to find implied volatility.
    Supports both scalar and vectorized operations.

    Attributes:
        risk_free_rate: Risk-free interest rate (default: 0.03)
        max_iterations: Maximum iterations for Newton-Raphson (default: 100)
        tolerance: Convergence tolerance (default: 1e-6)
        iv_min: Minimum IV bound (default: 0.001)
        iv_max: Maximum IV bound (default: 5.0)
    """

    # Numerical constants
    SQRT_2PI = np.sqrt(2.0 * np.pi)
    ONE_OVER_SQRT_2PI = 1.0 / np.sqrt(2.0 * np.pi)
    SQRT_2 = np.sqrt(2.0)

    # IV calculation bounds
    IV_MIN = 1e-6
    IV_MAX = 5.0  # 500% volatility cap
    IV_PRECISION = 1e-10
    MAX_ITERATIONS = 100
    DEFAULT_IV_MIN = 0.001  # Default for backward compatibility

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
        # Use DEFAULT_IV_MIN for backward compatibility
        self._iv_min = self.DEFAULT_IV_MIN
        self.iv_max = self.IV_MAX

    @property
    def iv_min(self) -> float:
        """Minimum IV bound."""
        return self._iv_min

    @iv_min.setter
    def iv_min(self, value: float):
        """Set minimum IV bound."""
        self._iv_min = value

    # ============ Normal Distribution Functions (Vectorized) ============

    @staticmethod
    def norm_cdf(x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """Standard normal cumulative distribution function (vectorized).

        Args:
            x: Input value(s)

        Returns:
            Cumulative probability
        """
        return stats.norm.cdf(x)

    @staticmethod
    def norm_pdf(x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """Standard normal probability density function (vectorized).

        Args:
            x: Input value(s)

        Returns:
            Probability density
        """
        return stats.norm.pdf(x)

    def _norm_cdf_scalar(self, x: float) -> float:
        """Calculate CDF for standard normal (scalar version using math.erf).

        Args:
            x: Input value

        Returns:
            Cumulative probability
        """
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _norm_pdf_scalar(self, x: float) -> float:
        """Calculate PDF for standard normal (scalar version).

        Args:
            x: Input value

        Returns:
            Probability density
        """
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    # Backward compatibility aliases
    def _norm_cdf(self, x: float) -> float:
        """Backward compatibility alias for norm_cdf (scalar)."""
        return float(self.norm_cdf(x))

    def _norm_pdf(self, x: float) -> float:
        """Backward compatibility alias for norm_pdf (scalar)."""
        return float(self.norm_pdf(x))

    # ============ Black-Scholes d1/d2 Parameters ============

    @classmethod
    def d1(
        cls,
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        r: float,
        sigma: Union[float, np.ndarray],
        T: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """Calculate Black-Scholes d1 parameter (vectorized).

        Args:
            S: Underlying asset price
            K: Strike price
            r: Risk-free interest rate
            sigma: Volatility
            T: Time to expiry in years

        Returns:
            d1 value(s)
        """
        with np.errstate(divide='ignore', invalid='ignore'):
            sqrt_T = np.sqrt(T)
            result = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
            # Handle invalid values
            result = np.where((sigma <= 0) | (T <= 0) | (S <= 0) | (K <= 0), np.nan, result)
            return result

    @classmethod
    def d2(
        cls,
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        r: float,
        sigma: Union[float, np.ndarray],
        T: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """Calculate Black-Scholes d2 parameter (vectorized).

        Args:
            S: Underlying asset price
            K: Strike price
            r: Risk-free interest rate
            sigma: Volatility
            T: Time to expiry in years

        Returns:
            d2 value(s)
        """
        return cls.d1(S, K, r, sigma, T) - sigma * np.sqrt(T)

    # ============ Black-Scholes Option Price ============

    @classmethod
    def bs_price(
        cls,
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        r: float,
        sigma: Union[float, np.ndarray],
        T: Union[float, np.ndarray],
        option_type: Union[str, CallOrPut, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """Calculate Black-Scholes option price (vectorized).

        Args:
            S: Underlying asset price (scalar or array)
            K: Strike price (scalar or array)
            r: Risk-free interest rate
            sigma: Volatility (scalar or array)
            T: Time to expiry in years (scalar or array)
            option_type: 'CALL'/'PUT' or CallOrPut enum (scalar or array-like)

        Returns:
            Theoretical option price
        """
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)

        d_1 = cls.d1(S, K, r, sigma, T)
        d_2 = d_1 - sigma * np.sqrt(T)

        discount = np.exp(-r * T)

        # Handle option type conversion
        if isinstance(option_type, CallOrPut):
            option_type = option_type.value
        elif isinstance(option_type, str):
            is_call = option_type.upper() == 'CALL'
            if is_call:
                price = S * cls.norm_cdf(d_1) - K * discount * cls.norm_cdf(d_2)
            else:
                price = K * discount * cls.norm_cdf(-d_2) - S * cls.norm_cdf(-d_1)

            # Handle invalid values
            price = np.where((sigma <= 0) | (T <= 0) | (S <= 0) | (K <= 0), np.nan, price)
            return price
        else:
            # Vectorized handling
            option_type = np.asarray(option_type)
            # Convert CallOrPut enum array to string if needed
            if hasattr(option_type, 'flatten'):
                option_type_str = np.char.upper(option_type.astype(str))
                is_call = option_type_str == 'CALL'
            else:
                is_call = np.char.upper(option_type.astype(str)) == 'CALL'

            call_price = S * cls.norm_cdf(d_1) - K * discount * cls.norm_cdf(d_2)
            put_price = K * discount * cls.norm_cdf(-d_2) - S * cls.norm_cdf(-d_1)
            price = np.where(is_call, call_price, put_price)

        # Handle invalid values
        price = np.where((sigma <= 0) | (T <= 0) | (S <= 0) | (K <= 0), np.nan, price)
        return price

    def _bs_price_scalar(
        self,
        S: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        option_type: CallOrPut
    ) -> float:
        """Calculate Black-Scholes option price (scalar version).

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
            price = S * self._norm_cdf_scalar(d1) - K * discount * self._norm_cdf_scalar(d2)
        else:
            price = K * discount * self._norm_cdf_scalar(-d2) - S * self._norm_cdf_scalar(-d1)

        return price

    def _bs_price(
        self,
        S: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        option_type: CallOrPut
    ) -> float:
        """Backward compatibility alias for bs_price (scalar version).

        Args:
            S: Underlying asset price
            K: Strike price
            r: Risk-free interest rate
            sigma: Volatility
            T: Time to expiry in years
            option_type: CALL or PUT

        Returns:
            Theoretical option price
        """
        return self._bs_price_scalar(S, K, r, sigma, T, option_type)

    # ============ Greeks Calculations ============

    @classmethod
    def delta(
        cls,
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        r: float,
        sigma: Union[float, np.ndarray],
        T: Union[float, np.ndarray],
        option_type: Union[str, CallOrPut, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """Calculate Delta (vectorized).

        Delta = dV/dS
        CALL: N(d1), PUT: N(d1) - 1

        Args:
            S: Underlying price
            K: Strike price
            r: Risk-free rate
            sigma: Volatility
            T: Time to expiry (years)
            option_type: 'CALL' or 'PUT'

        Returns:
            Delta value(s)
        """
        d_1 = cls.d1(S, K, r, sigma, T)

        if isinstance(option_type, CallOrPut):
            option_type = option_type.value

        if isinstance(option_type, str):
            is_call = option_type.upper() == 'CALL'
            if is_call:
                return cls.norm_cdf(d_1)
            else:
                return cls.norm_cdf(d_1) - 1
        else:
            option_type = np.asarray(option_type)
            is_call = np.char.upper(option_type.astype(str)) == 'CALL'
            call_delta = cls.norm_cdf(d_1)
            put_delta = call_delta - 1
            return np.where(is_call, call_delta, put_delta)

    @classmethod
    def gamma(
        cls,
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        r: float,
        sigma: Union[float, np.ndarray],
        T: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """Calculate Gamma (vectorized).

        Gamma = d2V/dS2 = N'(d1) / (S * sigma * sqrt(T))
        Gamma is the same for CALL and PUT.

        Args:
            S: Underlying price
            K: Strike price
            r: Risk-free rate
            sigma: Volatility
            T: Time to expiry (years)

        Returns:
            Gamma value(s)
        """
        S = np.asarray(S, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)

        d_1 = cls.d1(S, K, r, sigma, T)
        with np.errstate(divide='ignore', invalid='ignore'):
            gamma = cls.norm_pdf(d_1) / (S * sigma * np.sqrt(T))
            gamma = np.where((sigma <= 0) | (T <= 0) | (S <= 0), np.nan, gamma)
        return gamma

    @classmethod
    def theta(
        cls,
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        r: float,
        sigma: Union[float, np.ndarray],
        T: Union[float, np.ndarray],
        option_type: Union[str, CallOrPut, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """Calculate Theta (vectorized).

        Theta = dV/dt (per year)
        Returns negative value (time decay).

        Args:
            S: Underlying price
            K: Strike price
            r: Risk-free rate
            sigma: Volatility
            T: Time to expiry (years)
            option_type: 'CALL' or 'PUT'

        Returns:
            Theta value(s) per year
        """
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)

        d_1 = cls.d1(S, K, r, sigma, T)
        d_2 = d_1 - sigma * np.sqrt(T)

        sqrt_T = np.sqrt(T)
        discount = np.exp(-r * T)

        # First term: time value decay
        term1 = -S * cls.norm_pdf(d_1) * sigma / (2 * sqrt_T)

        if isinstance(option_type, CallOrPut):
            option_type = option_type.value

        if isinstance(option_type, str):
            is_call = option_type.upper() == 'CALL'
            if is_call:
                term2 = -r * K * discount * cls.norm_cdf(d_2)
            else:
                term2 = r * K * discount * cls.norm_cdf(-d_2)
        else:
            option_type = np.asarray(option_type)
            is_call = np.char.upper(option_type.astype(str)) == 'CALL'
            call_term2 = -r * K * discount * cls.norm_cdf(d_2)
            put_term2 = r * K * discount * cls.norm_cdf(-d_2)
            term2 = np.where(is_call, call_term2, put_term2)

        theta = term1 + term2
        theta = np.where((sigma <= 0) | (T <= 0) | (S <= 0) | (K <= 0), np.nan, theta)
        return theta

    @classmethod
    def vega(
        cls,
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        r: float,
        sigma: Union[float, np.ndarray],
        T: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """Calculate Vega (vectorized).

        Vega = dV/dsigma = S * sqrt(T) * N'(d1)
        Vega is the same for CALL and PUT.

        Args:
            S: Underlying price
            K: Strike price
            r: Risk-free rate
            sigma: Volatility
            T: Time to expiry (years)

        Returns:
            Vega value(s): Price change for 1% (0.01) volatility change
        """
        S = np.asarray(S, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)

        d_1 = cls.d1(S, K, r, sigma, T)
        vega = S * np.sqrt(T) * cls.norm_pdf(d_1)
        vega = np.where((sigma <= 0) | (T <= 0) | (S <= 0), np.nan, vega)
        return vega

    @classmethod
    def rho(
        cls,
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        r: float,
        sigma: Union[float, np.ndarray],
        T: Union[float, np.ndarray],
        option_type: Union[str, CallOrPut, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """Calculate Rho (vectorized).

        Rho = dV/dr
        CALL: K * T * e^(-rT) * N(d2)
        PUT: -K * T * e^(-rT) * N(-d2)

        Args:
            S: Underlying price
            K: Strike price
            r: Risk-free rate
            sigma: Volatility
            T: Time to expiry (years)
            option_type: 'CALL' or 'PUT'

        Returns:
            Rho value(s)
        """
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)

        d_1 = cls.d1(S, K, r, sigma, T)
        d_2 = d_1 - sigma * np.sqrt(T)

        discount = np.exp(-r * T)

        if isinstance(option_type, CallOrPut):
            option_type = option_type.value

        if isinstance(option_type, str):
            is_call = option_type.upper() == 'CALL'
            if is_call:
                rho = K * T * discount * cls.norm_cdf(d_2)
            else:
                rho = -K * T * discount * cls.norm_cdf(-d_2)
        else:
            option_type = np.asarray(option_type)
            is_call = np.char.upper(option_type.astype(str)) == 'CALL'
            call_rho = K * T * discount * cls.norm_cdf(d_2)
            put_rho = -K * T * discount * cls.norm_cdf(-d_2)
            rho = np.where(is_call, call_rho, put_rho)

        rho = np.where((sigma <= 0) | (T <= 0) | (S <= 0) | (K <= 0), np.nan, rho)
        return rho

    def _bs_vega_scalar(
        self,
        S: float,
        K: float,
        r: float,
        sigma: float,
        T: float
    ) -> float:
        """Calculate Black-Scholes Vega (scalar version).

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

        return S * self._norm_pdf_scalar(d1) * sqrt_T

    # ============ Implied Volatility Calculation ============

    def implied_volatility(
        self,
        price: Union[float, np.ndarray],
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        T: Union[float, np.ndarray],
        option_type: Union[str, CallOrPut, np.ndarray],
        init_sigma: Union[float, np.ndarray] = 0.3
    ) -> Union[float, np.ndarray]:
        """Calculate implied volatility using Newton-Raphson + bisection fallback.

        Enhanced version that handles edge cases:
        1. Deep ITM options (market price ~ intrinsic value)
        2. Market price < BS theoretical price (time value underestimated)
        3. Extreme ITM/OTM options

        Args:
            price: Option market price
            S: Underlying price
            K: Strike price
            T: Time to expiry (years)
            option_type: 'CALL' or 'PUT'
            init_sigma: Initial volatility guess

        Returns:
            Implied volatility (NaN if failed, small value for deep ITM)
        """
        price = np.asarray(price, dtype=np.float64)
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)
        init_sigma = np.asarray(init_sigma, dtype=np.float64)

        r = self.risk_free_rate

        # Handle option type
        if isinstance(option_type, CallOrPut):
            option_type = option_type.value

        # Ensure all arrays have same shape first
        shape = np.broadcast(price, S, K, T, init_sigma).shape
        price = np.broadcast_to(price, shape).copy()
        S = np.broadcast_to(S, shape).copy()
        K = np.broadcast_to(K, shape).copy()
        T = np.broadcast_to(T, shape).copy()
        init_sigma = np.broadcast_to(init_sigma, shape).copy()

        # Convert option_type to array with matching shape
        if isinstance(option_type, str):
            option_type = np.full(shape, option_type)
        else:
            option_type = np.asarray(option_type)
            if option_type.shape != shape:
                option_type = np.broadcast_to(option_type, shape).copy()

        # Initialize result
        result = np.full(shape, np.nan)

        # Check valid inputs
        is_call = np.char.upper(option_type.astype(str)) == 'CALL'

        # Calculate intrinsic value
        intrinsic_call = np.maximum(S - K, 0)
        intrinsic_put = np.maximum(K - S, 0)
        intrinsic = np.where(is_call, intrinsic_call, intrinsic_put)

        # Basic validity check (relaxed conditions)
        basic_valid = (price > 0) & (S > 0) & (K > 0) & (T > 1e-6)

        # Calculate time value
        time_value = price - intrinsic
        time_value_ratio = time_value / np.maximum(price, 1e-6)

        # Case 1: Market price < intrinsic value (arbitrage opportunity)
        below_intrinsic = basic_valid & (price < intrinsic * 0.999)
        result = np.where(below_intrinsic, 0.005, result)  # Set to 0.5% min IV

        # Case 2: Market price >= intrinsic but tiny time value (deep ITM)
        deep_itm_tiny_tv = basic_valid & (~below_intrinsic) & (time_value_ratio < 0.01)
        result = np.where(deep_itm_tiny_tv, 0.01, result)  # Set to 1% min IV

        # Case 3: Normal case (can solve for IV)
        valid = basic_valid & (~below_intrinsic)

        # Use improved Newton-Raphson method
        if np.any(valid):
            sigma = np.where(valid, init_sigma, np.nan)
            sigma = np.clip(sigma, self.IV_MIN, self.IV_MAX)

            # Fast iteration with relaxed convergence
            for iteration in range(self.MAX_ITERATIONS):
                # Calculate BS price and Vega
                bs_val = self.bs_price(S, K, r, sigma, T, option_type)
                vega_val = self.vega(S, K, r, sigma, T)

                # Calculate price difference
                diff = price - bs_val

                # Check convergence (relative or absolute error)
                rel_error = np.abs(diff) / np.maximum(price, 1e-6)
                converged = (np.abs(diff) < self.IV_PRECISION) | (rel_error < 1e-6) | (~valid)
                if np.all(converged):
                    break

                # Newton-Raphson update with damping and bounds
                with np.errstate(divide='ignore', invalid='ignore'):
                    delta_sigma = diff / np.maximum(vega_val, 1e-8)

                    # Adaptive step size limit
                    max_step = np.maximum(sigma * 0.5, 0.1)
                    delta_sigma = np.clip(delta_sigma, -max_step, max_step)

                    # Update sigma
                    new_sigma = sigma + delta_sigma

                    # Bounds check
                    new_sigma = np.clip(new_sigma, self.IV_MIN, self.IV_MAX)

                    # Only update unconverged values
                    sigma = np.where(converged, sigma, new_sigma)

            # Check final convergence
            final_bs = self.bs_price(S, K, r, sigma, T, option_type)
            final_diff = np.abs(price - final_bs)
            final_rel_error = final_diff / np.maximum(price, 1e-6)

            # Use calculated value for well-converged results
            good_convergence = (final_diff < 0.01) | (final_rel_error < 0.01)
            result = np.where(valid & good_convergence, sigma, result)

            # For unconverged but valid data, try bisection
            need_bisection = valid & (~good_convergence)
            if np.any(need_bisection):
                bisection_result = self._bisection_iv(
                    price[need_bisection], S[need_bisection], K[need_bisection],
                    r, T[need_bisection], option_type[need_bisection]
                )
                result[need_bisection] = bisection_result

        # For still invalid deep ITM options, check if market price < min theoretical
        still_nan = np.isnan(result) & basic_valid
        if np.any(still_nan):
            # Calculate min theoretical price (IV = 0.001)
            min_bs = self.bs_price(S, K, r, 0.001, T, option_type)
            # If market price < min theoretical, it's extreme deep ITM
            deep_itm_no_solution = still_nan & (price < min_bs * 1.01)
            result = np.where(deep_itm_no_solution, 0.005, result)

        # Return scalar or array
        if result.ndim == 0:  # 0-dimensional array (scalar input)
            return float(result)
        if result.shape == (1,):
            return float(result[0])
        return result

    def _bisection_iv(
        self,
        price: np.ndarray,
        S: np.ndarray,
        K: np.ndarray,
        r: float,
        T: np.ndarray,
        option_type: np.ndarray,
        max_iter: int = 50
    ) -> np.ndarray:
        """Bisection method for IV calculation (fallback, more stable but slower).

        Args:
            price: Option market price
            S: Underlying price
            K: Strike price
            r: Risk-free rate
            T: Time to expiry
            option_type: 'CALL' or 'PUT'
            max_iter: Maximum iterations

        Returns:
            Implied volatility
        """
        result = np.full(price.shape, np.nan)

        low = np.full(price.shape, self.IV_MIN)
        high = np.full(price.shape, self.IV_MAX)
        mid = np.full(price.shape, np.nan)

        for _ in range(max_iter):
            mid = (low + high) / 2
            bs_mid = self.bs_price(S, K, r, mid, T, option_type)

            # Update bounds
            too_high = bs_mid > price
            low = np.where(too_high, low, mid)
            high = np.where(too_high, mid, high)

            # Check convergence
            if np.all((high - low) < 1e-6):
                break

        result = mid
        return result

    def calculate_iv(
        self,
        option: OptionQuote,
        future_price: float,
        time_to_expiry: Optional[float] = None
    ) -> Optional[float]:
        """Calculate implied volatility for an option (legacy interface).

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

        # Use the vectorized method
        result = self.implied_volatility(
            price=option.last_price,
            S=future_price,
            K=option.strike_price,
            T=T,
            option_type=option.call_or_put
        )

        if isinstance(result, float) and np.isnan(result):
            return None
        return result

    # ============ Volatility Smile ============

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

    def calculate_smile_vectorized(
        self,
        strikes: np.ndarray,
        prices: np.ndarray,
        S: float,
        T: float,
        option_types: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate volatility smile (vectorized).

        Args:
            strikes: Array of strike prices
            prices: Array of option prices
            S: Underlying price
            T: Time to expiry (years)
            option_types: Array of option types ('CALL' or 'PUT')

        Returns:
            Tuple of (strikes, ivs) arrays
        """
        ivs = self.implied_volatility(
            price=prices,
            S=S,
            K=strikes,
            T=T,
            option_type=option_types
        )
        return strikes, ivs

    # ============ Greeks for OptionQuote ============

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

        # Use vectorized methods
        delta = self.delta(S, K, r, sigma, T, option.call_or_put)
        gamma = self.gamma(S, K, r, sigma, T)
        vega = self.vega(S, K, r, sigma, T)
        theta = self.theta(S, K, r, sigma, T, option.call_or_put)
        rho = self.rho(S, K, r, sigma, T, option.call_or_put)

        return {
            "delta": float(delta) if not np.isnan(delta) else None,
            "gamma": float(gamma) if not np.isnan(gamma) else None,
            "vega": float(vega) if not np.isnan(vega) else None,
            "theta": float(theta) / 365.0 if not np.isnan(theta) else None,  # Per day
            "rho": float(rho) / 100.0 if not np.isnan(rho) else None  # Per 1% rate change
        }

    def calculate_greeks_vectorized(
        self,
        S: Union[float, np.ndarray],
        K: Union[float, np.ndarray],
        r: float,
        sigma: Union[float, np.ndarray],
        T: Union[float, np.ndarray],
        option_type: Union[str, np.ndarray]
    ) -> dict:
        """Calculate all Greeks (vectorized).

        Args:
            S: Underlying price
            K: Strike price
            r: Risk-free rate
            sigma: Volatility
            T: Time to expiry (years)
            option_type: 'CALL' or 'PUT'

        Returns:
            Dictionary with delta, gamma, vega, theta, rho arrays
        """
        return {
            "delta": self.delta(S, K, r, sigma, T, option_type),
            "gamma": self.gamma(S, K, r, sigma, T),
            "vega": self.vega(S, K, r, sigma, T),
            "theta": self.theta(S, K, r, sigma, T, option_type),
            "rho": self.rho(S, K, r, sigma, T, option_type)
        }

    # ============ Helper Methods ============

    def _calculate_time_to_expiry(self, expiry_date) -> float:
        """Calculate time to expiry in years from expiry date.

        Args:
            expiry_date: Expiration date (datetime object or string)

        Returns:
            Time to expiry in years
        """
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


# ============ Convenience Functions ============

def calculate_option_iv(
    option_price: float,
    underlying_price: float,
    strike_price: float,
    time_to_expiry: float,
    option_type: str,
    risk_free_rate: float = 0.03
) -> Optional[float]:
    """Convenience function to calculate IV for a single option.

    Args:
        option_price: Option market price
        underlying_price: Current underlying price
        strike_price: Strike price
        time_to_expiry: Time to expiry in years
        option_type: 'CALL' or 'PUT'
        risk_free_rate: Risk-free interest rate

    Returns:
        Implied volatility or None if calculation fails
    """
    calculator = IVCalculator(risk_free_rate=risk_free_rate)
    result = calculator.implied_volatility(
        price=option_price,
        S=underlying_price,
        K=strike_price,
        T=time_to_expiry,
        option_type=option_type
    )
    if isinstance(result, float) and not np.isnan(result):
        return result
    return None


def calculate_option_greeks(
    underlying_price: float,
    strike_price: float,
    time_to_expiry: float,
    volatility: float,
    option_type: str,
    risk_free_rate: float = 0.03
) -> dict:
    """Convenience function to calculate Greeks for a single option.

    Args:
        underlying_price: Current underlying price
        strike_price: Strike price
        time_to_expiry: Time to expiry in years
        volatility: Volatility (decimal, e.g., 0.25 for 25%)
        option_type: 'CALL' or 'PUT'
        risk_free_rate: Risk-free interest rate

    Returns:
        Dictionary with delta, gamma, vega, theta, rho
    """
    calculator = IVCalculator(risk_free_rate=risk_free_rate)
    return calculator.calculate_greeks_vectorized(
        S=underlying_price,
        K=strike_price,
        r=risk_free_rate,
        sigma=volatility,
        T=time_to_expiry,
        option_type=option_type
    )