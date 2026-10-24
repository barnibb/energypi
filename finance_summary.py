"""Geldwerte der Tagesenergie; Netzbezug wird mit Tibber-Intervallen bewertet."""
import json

from database import connect


def _points(path, start, end):
    with connect(path) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'minute_archive', 'measurements'} <= tables:
            return []
        archived = db.execute(
            'SELECT payload FROM minute_archive WHERE minute>=? AND minute<? ORDER BY minute',
            (int(start // 60) * 60, end)).fetchall()
        rows = db.execute(
            'SELECT ts,total_act_power,error FROM measurements WHERE ts>=? AND ts<? ORDER BY ts',
            (start, end)).fetchall()
    points = [(p['first'], p['last'], p.get('total_act_power'), bool(p.get('error')))
              for row in archived for p in json.loads(row['payload']) if start <= p['ts'] < end]
    points.extend((r['ts'], r['ts'], r['total_act_power'], bool(r['error'])) for r in rows)
    return sorted(points, key=lambda point: point[0])


def _positive_wh(left, right, seconds):
    if left * right < 0:
        fraction = abs(left) / (abs(left) + abs(right))
        return (max(left, 0) * fraction + max(right, 0) * (1 - fraction)) * seconds / 2
    return (max(left, 0) + max(right, 0)) * seconds / 2


def financial_summary(path, start, end, flows, feed_in_ct):
    """Return actual import cost and explicitly labelled economic estimates."""
    with connect(path) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'tibber_prices', 'tibber_meta'} <= tables:
            prices = []
        else:
            meta = db.execute('SELECT home_id FROM tibber_meta WHERE id=1').fetchone()
            prices = db.execute(
                'SELECT starts_at,ends_at,total FROM tibber_prices '
                'WHERE home_id=? AND starts_at<? AND ends_at>? ORDER BY starts_at',
                (meta[0], end, start)).fetchall() if meta else []
    intervals = [(max(start, row['starts_at']), min(end, row['ends_at']), row['total'] * 100)
                 for row in prices if max(start, row['starts_at']) < min(end, row['ends_at'])]
    points = _points(path, start, end)
    import_wh = cost_eur = covered = priced = 0.0
    previous = None
    for first, last, power, error in points:
        if error or power is None:
            previous = None
            continue
        if previous is not None and 0 < first - previous[0] <= 15:
            a, b, p0, p1 = previous[0], first, previous[1], power
            duration = b - a
            covered += duration
            for price_start, price_end, price_ct in intervals:
                left, right = max(a, price_start), min(b, price_end)
                if left >= right:
                    continue
                wl = p0 + (p1 - p0) * (left - a) / duration
                wr = p0 + (p1 - p0) * (right - a) / duration
                wh = _positive_wh(wl, wr, right - left)
                import_wh += wh
                cost_eur += wh / 3600000 * price_ct / 100
                priced += right - left
        if last > first:
            duration = last - first
            covered += duration
            for price_start, price_end, price_ct in intervals:
                overlap = max(0, min(last, price_end) - max(first, price_start))
                if overlap:
                    wh = max(power, 0) * overlap
                    import_wh += wh
                    cost_eur += wh / 3600000 * price_ct / 100
                    priced += overlap
        previous = (last, power)
    weighted_seconds = sum(b - a for a, b, _ in intervals)
    average_ct = (sum((b - a) * price for a, b, price in intervals) / weighted_seconds
                  if weighted_seconds else None)
    price_coverage = priced / covered if covered else 0
    complete = bool(flows.get('valid') and average_ct is not None and price_coverage >= .95)
    pv_direct = None
    if flows.get('pv_kwh') is not None and flows.get('export_kwh') is not None and flows.get('battery_in_kwh') is not None:
        pv_direct = max(0.0, flows['pv_kwh'] - flows['export_kwh'] - flows['battery_in_kwh'])
    feed_revenue = flows.get('export_kwh') * feed_in_ct / 100 if flows.get('export_kwh') is not None else None
    pv_benefit = (pv_direct * max(0, average_ct - feed_in_ct) / 100
                  if pv_direct is not None and average_ct is not None else None)
    battery_value = (flows.get('battery_out_kwh') * average_ct / 100
                     if flows.get('battery_out_kwh') is not None and average_ct is not None else None)
    values = (feed_revenue, pv_benefit, battery_value)
    priced_import_kwh=import_wh / 3600000
    actual_import_price_ct=(cost_eur/priced_import_kwh*100
                            if complete and priced_import_kwh>0 else None)
    effective_house_price_ct=((cost_eur-feed_revenue)/flows['house_kwh']*100
                              if complete and flows.get('house_kwh',0)>0 else None)
    return dict(import_cost_eur=cost_eur if complete else None,
                priced_import_kwh=priced_import_kwh if complete else None,
                actual_import_price_ct=actual_import_price_ct,
                effective_house_price_ct=effective_house_price_ct,
                price_coverage=price_coverage,average_price_ct=average_ct,
                pv_direct_kwh=pv_direct,feed_revenue_eur=feed_revenue if complete else None,
                pv_benefit_eur=pv_benefit if complete else None,
                battery_value_eur=battery_value if complete else None,
                benefit_eur=sum(values) if complete and all(v is not None for v in values) else None,
                complete=complete,
                note=('Netzbezug mit Tibber-Viertelstundenpreisen. PV-Nutzen und Akku-Bruttowert '
                      'mit dem zeitgewichteten Preis; Akku-Ladekosten und Verluste sind nicht abgezogen.'))
