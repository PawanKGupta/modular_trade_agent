
from core.analysis import analyze_ticker
from core.scoring import compute_strength_score
from core.telegram import send_telegram
from core.scrapping import get_stock_list
from utils.logger import logger

def get_stocks():
    # stocks = get_stock_list()
    stocks = "NAVA, GLENMARK, VGL, HYUNDAI, ENRIN, OLECTRA, DDEVPLSTIK, CURAA, SUDARSCHEM, SMLISUZU"
    return [s.strip().upper() + ".NS" for s in stocks.split(",")]

def main():
    tickers = get_stocks()
    results = []

    for t in tickers:
        try:
            r = analyze_ticker(t)
            results.append(r)
            
            # Log based on analysis status
            if r.get('status') == 'success':
                logger.debug(f"SUCCESS {t}: {r['verdict']}")
            else:
                logger.warning(f"WARNING {t}: {r.get('status', 'unknown_error')} - {r.get('error', 'No details')}")
                
        except Exception as e:
            logger.error(f"ERROR Unexpected error analyzing {t}: {e}")
            results.append({"ticker": t, "status": "fatal_error", "error": str(e)})

    results.sort(key=lambda x: -compute_strength_score(x))

    buys = [r for r in results if r.get('verdict') == 'buy']

    if buys:
        msg = "*Reversal Buy Candidates (today)*\n"
        for b in buys:
            buy_low, buy_high = b['buy_range']
            target = b['target']
            stop = b['stop']
            rsi = b['rsi']
            msg += f"{b['ticker']}: Buy ({buy_low:.2f}, {buy_high:.2f}) Target {target:.2f} Stop {stop:.2f} (rsi={rsi})\n"
        send_telegram(msg)
    else:
        logger.info("No buy candidates today.")

if __name__ == "__main__":
    main()
