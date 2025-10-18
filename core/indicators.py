import pandas_ta as ta
from ta.trend  import ADXIndicator

from utils.logger import logger


def compute_indicators(df):
    if df is None or df.empty:
        return None

    try:
        df = df.copy()
        df['rsi14'] = ta.rsi(df['close'], length=10)
        df['ema20'] = ta.ema(df['close'], length=20)
        df['ema50'] = ta.ema(df['close'], length=50)
        # df['adx'] = ta.adx(df['high'], df['low'], df['close'], length=14)['ADX_14']
        # adx = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
        # df['adx'] = adx.adx()

        return df
    except Exception as e:
        logger.exception("Error computing indicators")
        return None
