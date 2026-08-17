import pandas as pd
from services.finance_api import calculate_rsi, calculate_sma


def test_sma_simple():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    sma3 = calculate_sma(s, 3)
    # rolling mean with window=3: [1, (1+2)/2, (1+2+3)/3, (2+3+4)/3, (3+4+5)/3]
    assert round(sma3.iloc[0], 6) == 1.0
    assert round(sma3.iloc[1], 6) == 1.5
    assert round(sma3.iloc[2], 6) == 2.0
    assert round(sma3.iloc[3], 6) == 3.0
    assert round(sma3.iloc[4], 6) == 4.0


def test_rsi_constant():
    # RSI of a flat series should be 50 (neutral) by our fillna
    s = pd.Series([100.0] * 30)
    rsi = calculate_rsi(s, window=14)
    # drop initial NaNs
    tail = rsi.dropna()
    assert all(v == 50 for v in tail)


def test_rsi_uptrend():
    # monotonic increasing prices -> high RSI
    s = pd.Series([float(i) for i in range(1, 31)])
    rsi = calculate_rsi(s, window=14)
    last = float(rsi.dropna().iloc[-1])
    assert last > 60
