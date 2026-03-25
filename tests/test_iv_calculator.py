# tests/test_iv_calculator.py
"""Tests for IV Calculator module."""
import pytest
from datetime import date, timedelta

from core.models import CallOrPut, OptionQuote
from core.iv_calculator import IVCalculator


def create_option(
    symbol: str,
    strike_price: float,
    call_or_put: CallOrPut,
    last_price: float,
    days_to_expiry: int = 30
) -> OptionQuote:
    """Helper to create OptionQuote with default values for required fields."""
    expire_date = date.today() + timedelta(days=days_to_expiry)
    return OptionQuote(
        symbol=symbol,
        underlying="UNDERLYING",
        exchange_id="EXCHANGE",
        strike_price=strike_price,
        call_or_put=call_or_put,
        last_price=last_price,
        bid_price=last_price * 0.98,
        ask_price=last_price * 1.02,
        volume=1000,
        open_interest=500,
        expire_date=expire_date
    )


class TestIVCalculatorCreation:
    """Test IVCalculator creation and configuration."""

    def test_default_creation(self):
        """Test creating calculator with default parameters."""
        calc = IVCalculator()
        assert calc.risk_free_rate == 0.03
        assert calc.max_iterations == 100
        assert calc.tolerance == 1e-6
        assert calc.iv_min == 0.001
        assert calc.iv_max == 5.0

    def test_custom_parameters(self):
        """Test creating calculator with custom parameters."""
        calc = IVCalculator(
            risk_free_rate=0.05,
            max_iterations=50,
            tolerance=1e-8
        )
        assert calc.risk_free_rate == 0.05
        assert calc.max_iterations == 50
        assert calc.tolerance == 1e-8


class TestNormalDistribution:
    """Test normal distribution functions."""

    def test_norm_cdf_at_zero(self):
        """Test CDF at zero is 0.5."""
        calc = IVCalculator()
        assert abs(calc._norm_cdf(0) - 0.5) < 1e-10

    def test_norm_cdf_symmetry(self):
        """Test CDF symmetry: CDF(-x) = 1 - CDF(x)."""
        calc = IVCalculator()
        x = 1.5
        assert abs(calc._norm_cdf(-x) - (1 - calc._norm_cdf(x))) < 1e-10

    def test_norm_pdf_at_zero(self):
        """Test PDF at zero."""
        calc = IVCalculator()
        expected = 1.0 / (2.0 * 3.141592653589793) ** 0.5
        assert abs(calc._norm_pdf(0) - expected) < 1e-10

    def test_norm_pdf_symmetry(self):
        """Test PDF is symmetric."""
        calc = IVCalculator()
        assert abs(calc._norm_pdf(1) - calc._norm_pdf(-1)) < 1e-10


class TestBSPrice:
    """Test Black-Scholes price calculation."""

    @pytest.fixture
    def calc(self):
        """Create IV calculator."""
        return IVCalculator(risk_free_rate=0.03)

    def test_call_price_atm(self, calc):
        """Test call price at-the-money."""
        # ATM call with 1 year to expiry
        S = 100.0  # Spot
        K = 100.0  # Strike (ATM)
        r = 0.03   # Risk-free rate
        sigma = 0.2  # 20% volatility
        T = 1.0   # 1 year

        price = calc._bs_price(S, K, r, sigma, T, CallOrPut.CALL)

        # Price should be positive
        assert price > 0

        # For ATM call, approximate price can be verified
        # Using put-call parity later
        assert 5 < price < 15  # Reasonable range

    def test_put_price_atm(self, calc):
        """Test put price at-the-money."""
        S = 100.0
        K = 100.0
        r = 0.03
        sigma = 0.2
        T = 1.0

        price = calc._bs_price(S, K, r, sigma, T, CallOrPut.PUT)

        assert price > 0
        assert 3 < price < 12  # Reasonable range

    def test_put_call_parity(self, calc):
        """Test put-call parity: C - P = S - K*e^(-rT)."""
        S = 100.0
        K = 100.0
        r = 0.03
        sigma = 0.2
        T = 1.0

        call_price = calc._bs_price(S, K, r, sigma, T, CallOrPut.CALL)
        put_price = calc._bs_price(S, K, r, sigma, T, CallOrPut.PUT)

        # Put-call parity
        expected_diff = S - K * pow(2.718281828, -r * T)
        actual_diff = call_price - put_price

        assert abs(actual_diff - expected_diff) < 0.01

    def test_itm_call_greater_than_otm_call(self, calc):
        """Test ITM call is worth more than OTM call."""
        S = 100.0
        K_itm = 90.0   # ITM for call
        K_otm = 110.0   # OTM for call
        r = 0.03
        sigma = 0.2
        T = 1.0

        itm_price = calc._bs_price(S, K_itm, r, sigma, T, CallOrPut.CALL)
        otm_price = calc._bs_price(S, K_otm, r, sigma, T, CallOrPut.CALL)

        assert itm_price > otm_price


class TestIVCalculation:
    """Test implied volatility calculation."""

    @pytest.fixture
    def calc(self):
        """Create IV calculator."""
        return IVCalculator(risk_free_rate=0.03)

    @pytest.fixture
    def atm_call(self):
        """Create ATM call option."""
        return create_option("CALL_100", 100.0, CallOrPut.CALL, 2.5, 30)

    @pytest.fixture
    def itm_call(self):
        """Create ITM call option."""
        return create_option("CALL_95", 95.0, CallOrPut.CALL, 6.5, 30)

    @pytest.fixture
    def otm_call(self):
        """Create OTM call option."""
        return create_option("CALL_105", 105.0, CallOrPut.CALL, 0.8, 30)

    @pytest.fixture
    def atm_put(self):
        """Create ATM put option."""
        return create_option("PUT_100", 100.0, CallOrPut.PUT, 2.3, 30)

    def test_calculator_creation(self, calc):
        """Test calculator is created correctly."""
        assert calc is not None
        assert calc.risk_free_rate == 0.03

    def test_iv_calculation_atm_call(self, calc, atm_call):
        """Test IV calculation for ATM call option."""
        future_price = 100.0  # ATM
        time_to_expiry = 30 / 365.0  # 30 days

        iv = calc.calculate_iv(atm_call, future_price, time_to_expiry)

        # IV should be positive and reasonable
        assert iv is not None
        assert 0.01 < iv < 2.0

    def test_iv_calculation_itm_call(self, calc, itm_call):
        """Test IV calculation for ITM call option."""
        future_price = 100.0
        time_to_expiry = 30 / 365.0

        iv = calc.calculate_iv(itm_call, future_price, time_to_expiry)

        # IV should be positive and reasonable
        assert iv is not None
        assert 0.01 < iv < 2.0

    def test_iv_calculation_otm_call(self, calc, otm_call):
        """Test IV calculation for OTM call option."""
        future_price = 100.0
        time_to_expiry = 30 / 365.0

        iv = calc.calculate_iv(otm_call, future_price, time_to_expiry)

        # IV should be positive and reasonable
        # May return None for very deep OTM
        if iv is not None:
            assert 0.01 < iv < 2.0

    def test_iv_calculation_put(self, calc, atm_put):
        """Test IV calculation for put option."""
        future_price = 100.0
        time_to_expiry = 30 / 365.0

        iv = calc.calculate_iv(atm_put, future_price, time_to_expiry)

        assert iv is not None
        assert 0.01 < iv < 2.0

    def test_iv_negative_price_raises_error(self, calc):
        """Test that negative option price raises ValueError."""
        # OptionQuote validates last_price >= 0 in __post_init__,
        # but we test the iv_calculator's validation
        # For this test, we create an option with valid price first
        # and check if the calculator properly validates
        option = create_option("CALL_100", 100.0, CallOrPut.CALL, 0.01, 30)
        # The validation in IVCalculator checks for last_price <= 0
        # Since OptionQuote already validates, we test the calculator directly
        # by checking it handles zero properly
        option.last_price = 0.0  # Bypass dataclass validation
        with pytest.raises(ValueError, match="Option price must be positive"):
            calc.calculate_iv(option, 100.0, 30/365.0)

    def test_iv_negative_future_price_raises_error(self, calc, atm_call):
        """Test that negative future price raises ValueError."""
        with pytest.raises(ValueError, match="Future price must be positive"):
            calc.calculate_iv(atm_call, -100.0, 30/365.0)

    def test_iv_zero_future_price_raises_error(self, calc, atm_call):
        """Test that zero future price raises ValueError."""
        with pytest.raises(ValueError, match="Future price must be positive"):
            calc.calculate_iv(atm_call, 0.0, 30/365.0)

    def test_iv_expired_option_returns_none(self, calc):
        """Test that expired option returns None."""
        # Create an option that's already expired
        option = create_option("CALL_100", 100.0, CallOrPut.CALL, 2.5, -10)
        iv = calc.calculate_iv(option, 100.0)
        assert iv is None

    def test_iv_convergence(self, calc):
        """Test that calculated IV can reproduce the price."""
        # Create an option with known parameters
        S = 100.0
        K = 100.0
        r = 0.03
        sigma = 0.25  # 25% volatility
        T = 30 / 365.0

        # Calculate theoretical price
        theoretical_price = calc._bs_price(S, K, r, sigma, T, CallOrPut.CALL)

        # Create option quote
        option = create_option("CALL_100", K, CallOrPut.CALL, theoretical_price, 30)

        # Calculate IV
        iv = calc.calculate_iv(option, S, T)

        # IV should be close to original sigma
        assert iv is not None
        assert abs(iv - sigma) < 0.01  # Within 1%


class TestIVSmile:
    """Test volatility smile calculation."""

    @pytest.fixture
    def calc(self):
        """Create IV calculator."""
        return IVCalculator(risk_free_rate=0.03)

    def test_calculate_smile(self, calc):
        """Test volatility smile calculation."""
        future_price = 100.0
        time_to_expiry = 30 / 365.0

        # Create options across different strikes
        options = []
        for strike in [90, 95, 100, 105, 110]:
            # Generate prices with slight smile pattern
            if strike < future_price:
                # ITM call - higher price
                price = max(0.5, future_price - strike + 3)
            elif strike > future_price:
                # OTM call - lower price
                price = max(0.3, 5 - (strike - future_price) * 0.3)
            else:
                # ATM
                price = 3.0

            option = create_option(f"CALL_{strike}", float(strike), CallOrPut.CALL, price)
            options.append(option)

        smile = calc.calculate_smile(options, future_price, time_to_expiry)

        # Should return same number of results
        assert len(smile) == len(options)

        # Each result should be (strike, iv) tuple
        for strike, iv in smile:
            assert isinstance(strike, float)
            if iv is not None:
                assert 0.01 < iv < 2.0


class TestGreeks:
    """Test Greeks calculation."""

    @pytest.fixture
    def calc(self):
        """Create IV calculator."""
        return IVCalculator(risk_free_rate=0.03)

    def test_calculate_greeks(self, calc):
        """Test Greeks calculation."""
        option = create_option("CALL_100", 100.0, CallOrPut.CALL, 3.0, 30)

        future_price = 100.0
        iv = 0.25
        time_to_expiry = 30 / 365.0

        greeks = calc.calculate_greeks(option, future_price, iv, time_to_expiry)

        # Check all Greeks are present
        assert "delta" in greeks
        assert "gamma" in greeks
        assert "vega" in greeks
        assert "theta" in greeks
        assert "rho" in greeks

        # Check reasonable values
        assert 0 < greeks["delta"] < 1  # Call delta is positive
        assert greeks["gamma"] > 0
        assert greeks["vega"] > 0
        assert greeks["theta"] < 0  # Time decay
        assert greeks["rho"] > 0  # Call rho is positive

    def test_put_delta_negative(self, calc):
        """Test that put delta is negative."""
        option = create_option("PUT_100", 100.0, CallOrPut.PUT, 3.0, 30)

        greeks = calc.calculate_greeks(option, 100.0, 0.25, 30/365.0)

        assert greeks["delta"] < 0


class TestEdgeCases:
    """Test edge cases for IV calculation."""

    @pytest.fixture
    def calc(self):
        """Create IV calculator."""
        return IVCalculator(risk_free_rate=0.03)

    def test_deep_otm_call(self, calc):
        """Test deep OTM call option."""
        # Deep OTM call - strike much higher than future price
        option = create_option("CALL_150", 150.0, CallOrPut.CALL, 0.01, 30)

        iv = calc.calculate_iv(option, 100.0, 30/365.0)

        # May return None or a very high IV
        if iv is not None:
            # Should be within bounds
            assert calc.iv_min <= iv <= calc.iv_max

    def test_deep_itm_call(self, calc):
        """Test deep ITM call option."""
        # Deep ITM call - strike much lower than future price
        # Price close to intrinsic value
        option = create_option("CALL_50", 50.0, CallOrPut.CALL, 50.5, 30)

        iv = calc.calculate_iv(option, 100.0, 30/365.0)

        # Should return minimum IV for deep ITM
        if iv is not None:
            assert iv >= calc.iv_min

    def test_zero_price_option(self, calc):
        """Test option with zero price."""
        # OptionQuote validates price >= 0, but IVCalculator also checks
        # We bypass dataclass validation by setting after creation
        option = create_option("CALL_100", 100.0, CallOrPut.CALL, 0.01, 30)
        option.last_price = 0.0

        with pytest.raises(ValueError, match="Option price must be positive"):
            calc.calculate_iv(option, 100.0, 30/365.0)

    def test_very_short_expiry(self, calc):
        """Test option with very short time to expiry."""
        # 1 hour to expiry
        option = create_option("CALL_100", 100.0, CallOrPut.CALL, 0.5, 0)

        iv = calc.calculate_iv(option, 100.0)

        # May return None or a valid IV
        if iv is not None:
            assert calc.iv_min <= iv <= calc.iv_max

    def test_long_expiry(self, calc):
        """Test option with long time to expiry."""
        option = create_option("CALL_100", 100.0, CallOrPut.CALL, 10.0, 365)

        iv = calc.calculate_iv(option, 100.0)

        assert iv is not None
        assert calc.iv_min <= iv <= calc.iv_max