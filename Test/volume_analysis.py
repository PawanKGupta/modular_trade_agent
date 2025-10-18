import pandas as pd

df = pd.read_csv('nse_buy_signal_with_reversal.csv')

print('📊 COMPLETE VOLUME-OPTIMIZED TRADING ANALYSIS')
print('='*50)

print('\n💰 MONEY SAVED BY VOLUME TIMING:')
print(f'  • Average decline saved: {df["DeclineSaved%"].mean():.2f}%')
print(f'  • Maximum decline saved: {df["DeclineSaved%"].max():.2f}%')
print(f'  • Profitable delays: {(df["DeclineSaved%"] > 0).sum()}/{len(df)} cases')

print('\n📈 SUCCESS RATE IMPROVEMENT:')
next_success = (df['NextDayResult'] == 'Yes').sum()
opt_success = (df['OptimalResult'] == 'Yes').sum()
print(f'  • Next day buying: {next_success}/{len(df)} ({next_success/len(df)*100:.1f}%)')
print(f'  • Volume-timed buying: {opt_success}/{len(df)} ({opt_success/len(df)*100:.1f}%)')
print(f'  • Improvement: +{opt_success - next_success} successful trades')

print('\n🔊 VOLUME PATTERN INSIGHTS:')
vol_spikes = df[df['OptimalBuyReason'].str.contains('Volume spike', na=False)]
print(f'  • Volume spikes detected: {len(vol_spikes)}/{len(df)} cases')
if len(vol_spikes) > 0:
    print(f'  • Avg volume ratio on spikes: {vol_spikes["VolumeRatio"].mean():.1f}x')

print('\n🎯 KEY STRATEGY:')
print('  • Wait 1-5 days after signal for volume confirmation')
print('  • Look for 1.5x+ volume with price bottoming')
print('  • Can save 1-20% on entry price while improving success rate')

print('\n🏆 BEST EXAMPLES:')
best = df[df['DeclineSaved%'] > 5].nlargest(3, 'DeclineSaved%')
for _, row in best.iterrows():
    print(f"  • {row['Ticker']}: Saved {row['DeclineSaved%']:.1f}% with {row['VolumeRatio']}x volume")