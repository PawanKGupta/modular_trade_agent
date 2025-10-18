def compute_strength_score(entry):
    score = 0
    if entry.get('verdict') != 'buy':
        return -1

    justifications = entry.get('justification', [])

    for j in justifications:
        if j.startswith('pattern:'):
            patterns = j.replace('pattern:', '').split(',')
            score += len(patterns) * 2
        elif j == 'volume_strong':
            score += 1
        elif j.startswith('rsi:'):
            try:
                rsi_val = float(j.split(':')[1])
                if rsi_val < 30:
                    score += 1
                if rsi_val < 20:
                    score += 1
            except Exception:
                pass

    return score
