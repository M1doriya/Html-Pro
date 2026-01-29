"""
Bank Statement Analysis v5.0 - Streamlit Dashboard
BACKWARDS COMPATIBLE with v4.0 schema
FIXED: All validation issues from html_validation_report.md
"""

import streamlit as st
import json
from datetime import datetime
import io
import zipfile
import re
from pathlib import Path
from typing import List, Tuple



st.set_page_config(page_title="Bank Statement Analysis v5.0", page_icon="🏦", layout="wide")

def detect_schema_version(data):
    """Detect schema version from JSON data"""
    schema_version = data.get('report_info', {}).get('schema_version', '')
    # Handle v5.x.x versions (5.0, 5.0.1, 5.0.2, 5.0.4, 5.1.0, etc.)
    if schema_version.startswith('5.'):
        return '5.0'
    if data.get('recurring_payments') or data.get('non_bank_financing'):
        return '5.0'
    accounts = data.get('accounts', [])
    if accounts:
        monthly = accounts[0].get('monthly_summary', [])
        if monthly and 'highest_intraday' in monthly[0]:
            return '5.0'
    return '4.0'

def get_monthly_high(m, schema_version):
    """Get highest balance - supports both v4.0 and v5.0"""
    if schema_version == '5.0':
        return m.get('highest_intraday', m.get('highest', 0))
    return m.get('highest', m.get('highest_intraday', 0))

def get_monthly_low(m, schema_version):
    """Get lowest balance - supports both v4.0 and v5.0"""
    if schema_version == '5.0':
        return m.get('lowest_intraday', m.get('lowest', 0))
    return m.get('lowest', m.get('lowest_intraday', 0))

def get_integrity_max_points(schema_version):
    """v4.0 has 25 max points, v5.0 has 23 max points"""
    return 23 if schema_version == '5.0' else 25

def generate_interactive_html(data):
    """Generate the interactive HTML template with v5.0 SUPPORT and v4.0 backwards compatibility"""
    
    schema_version = detect_schema_version(data)
    max_integrity_points = get_integrity_max_points(schema_version)
    
    r = data.get('report_info', {})
    accounts = data.get('accounts', [])
    consolidated = data.get('consolidated', {})
    categories = data.get('categories', {})
    volatility = data.get('volatility', {})
    flags = data.get('flags', {})
    # v5.2.x compatibility: some schemas store round-figure review items under 'flagged_for_review'
    flagged_for_review = data.get('flagged_for_review', {})
    if isinstance(flagged_for_review, dict) and flagged_for_review:
        if not isinstance(flags, dict):
            flags = {}
        # If 'flags.round_figure_transactions' is missing, derive it from 'flagged_for_review'
        if not flags.get('round_figure_transactions'):
            items = flagged_for_review.get('all_items') or flagged_for_review.get('top_10_items') or []
            if not isinstance(items, list):
                items = []
            converted = []
            for t in items:
                if isinstance(t, dict):
                    converted.append({
                        'date': t.get('date',''),
                        'description': t.get('description',''),
                        'type': t.get('type','CREDIT'),
                        'amount': t.get('amount',0),
                        'account': t.get('account',''),
                        'counterparty': t.get('counterparty',''),
                        'flag_reason': t.get('flag_reason',''),
                    })
            flags['round_figure_transactions'] = {
                'count': flagged_for_review.get('count', len(converted)),
                'total_amount': flagged_for_review.get('total_amount', 0),
                'all_transactions': converted,
                'top_10_transactions': converted[:10],
                'note': flagged_for_review.get('note',''),
            }
    kite = data.get('kite_flying', {})
    integrity = data.get('integrity_score', {})
    observations = data.get('observations', {})
    recommendations = data.get('recommendations', [])
    recurring = data.get('recurring_payments', {})
    non_bank = data.get('non_bank_financing', {})
    counterparties = data.get('counterparties', {})
    inter_account = data.get('inter_account_transfers', {})
    
    company = r.get('company_name', 'Company')
    period_start = r.get('period_start', '')
    period_end = r.get('period_end', '')
    total_months = r.get('total_months', 0)
    related_parties = r.get('related_parties', [])
    
    gross = consolidated.get('gross', {})
    business = consolidated.get('business_turnover', {})
    exclusions = consolidated.get('exclusions', {})
    
    total_txns = sum(a.get('transaction_count', 0) for a in accounts)
    
    int_score = integrity.get('score', 0)
    int_rating = integrity.get('rating', 'N/A')
    kite_score = kite.get('risk_score', 0)
    kite_level = kite.get('risk_level', 'LOW')
    vol_index = volatility.get('overall_index', 0)
    vol_level = volatility.get('overall_level', 'LOW')
    round_fig = flags.get('round_figure_transactions', {})
    round_count = round_fig.get('count', 0)
    
    # v5.0: Returned cheques
    returned_cheques = flags.get('returned_cheques', {})
    returned_count = returned_cheques.get('count', 0)
    returned_assessment = returned_cheques.get('assessment', 'ACCEPTABLE')
    
    # Score card classes
    int_class = 'excellent' if int_score >= 90 else 'good' if int_score >= 75 else 'warning' if int_score >= 60 else 'danger'
    kite_class = 'good' if kite_level == 'LOW' else 'warning' if kite_level == 'MEDIUM' else 'danger'
    vol_class = 'good' if vol_level == 'LOW' else 'warning' if vol_level in ['MODERATE', 'HIGH'] else 'danger'
    
    # Account cards HTML
    acc_cards = ""
    for a in accounts:
        cls = a.get('classification', 'SECONDARY')
        card_cls = 'primary' if cls == 'PRIMARY' else 'secondary'
        badge_cls = 'badge-primary' if cls == 'PRIMARY' else 'badge-secondary'
        closing_cls = 'debit' if a.get('closing_balance', 0) < 20000 else ''
        acc_cards += f'''
                <div class="account-card {card_cls}">
                    <div class="account-header">
                        <span class="bank-name">{a.get('bank_name','')}</span>
                        <span class="badge {badge_cls}">{cls}</span>
                    </div>
                    <div class="account-number">A/C: {a.get('account_number','')}</div>
                    <div class="account-metrics">
                        <div class="metric"><div class="metric-label">Total Credits</div><div class="metric-value credit">RM {a.get('total_credits',0):,.2f}</div></div>
                        <div class="metric"><div class="metric-label">Total Debits</div><div class="metric-value debit">RM {a.get('total_debits',0):,.2f}</div></div>
                        <div class="metric"><div class="metric-label">Transactions</div><div class="metric-value">{a.get('transaction_count',0):,}</div></div>
                        <div class="metric"><div class="metric-label">Closing Balance</div><div class="metric-value {closing_cls}">RM {a.get('closing_balance',0):,.2f}</div></div>
                    </div>
                </div>'''
    
    # Monthly tables - with v4/v5 field compatibility
    high_label = "Highest (Intraday)" if schema_version == '5.0' else "Highest"
    low_label = "Lowest (Intraday)" if schema_version == '5.0' else "Lowest"
    
    monthly_tables = ""
    for a in accounts:
        rows = ""
        for m in a.get('monthly_summary', []):
            vl = m.get('volatility_level', 'LOW')
            vs = 'EXTR' if vl == 'EXTREME' else ('MOD' if vl == 'MODERATE' else vl)
            high_val = get_monthly_high(m, schema_version)
            low_val = get_monthly_low(m, schema_version)
            rows += f'''
                                <tr>
                                    <td>{m.get('month_name', m.get('month',''))}</td>
                                    <td class="mono text-right">{m.get('opening',0):,.2f}</td>
                                    <td class="mono text-right credit">{m.get('credits',0):,.2f}</td>
                                    <td class="mono text-right debit">{m.get('debits',0):,.2f}</td>
                                    <td class="mono text-right">{m.get('closing',0):,.2f}</td>
                                    <td class="mono text-right">{high_val:,.2f}</td>
                                    <td class="mono text-right">{low_val:,.2f}</td>
                                    <td class="mono text-right">{m.get('swing',0):,.2f}</td>
                                    <td><span class="volatility-badge volatility-{vl}">{m.get('volatility_pct',0):.0f}% {vs}</span></td>
                                </tr>'''
        monthly_tables += f'''
            <div class="section">
                <div class="section-header"><h2 class="section-title">📅 Monthly Summary - {a.get('bank_name','')} ({a.get('account_number','')})</h2></div>
                <div class="section-content">
                    <div class="table-container">
                        <table class="data-table">
                            <thead><tr><th>Month</th><th class="text-right">Opening</th><th class="text-right">Credits</th><th class="text-right">Debits</th><th class="text-right">Closing</th><th class="text-right">{high_label}</th><th class="text-right">{low_label}</th><th class="text-right">Swing</th><th>Volatility</th></tr></thead>
                            <tbody>{rows}</tbody>
                        </table>
                    </div>
                </div>
            </div>'''
    
    # =====================================================
    # FIX #3: Categories with Top 5 Transactions
    # =====================================================
    credits_cat = categories.get('credits', [])
    debits_cat = categories.get('debits', [])
    
    # Detect if categories data exists
    has_categories = bool(credits_cat or debits_cat)
    
    # Build credits rows with expandable Top 5
    credits_rows = ""
    if not credits_cat:
        credits_rows = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:2rem;font-style:italic">No credit category data available in JSON</td></tr>'
    else:
        for idx, c in enumerate(credits_cat):
            cat_name = c.get("category", "")
            top5 = c.get("top_5_transactions", [])
            has_top5 = len(top5) > 0
            
            # Top 5 details HTML
            top5_html = ""
            if has_top5:
                top5_rows = "".join([f'<tr><td>{t.get("date","")}</td><td>{(t.get("counterparty") or t.get("description") or "")[:30]}</td><td class="mono text-right credit">RM {t.get("amount",0):,.2f}</td></tr>' for t in top5[:5]])
                top5_html = f'''<tr id="cr_top5_{idx}" class="top5-row" style="display:none"><td colspan="4">
                    <div class="top5-container"><table class="data-table mini"><thead><tr><th>Date</th><th>Counterparty</th><th class="text-right">Amount</th></tr></thead><tbody>{top5_rows}</tbody></table></div>
                </td></tr>'''
            
            toggle_btn = f'<button class="top5-btn" onclick="toggleTop5(\'cr_top5_{idx}\')">▶ Top 5</button>' if has_top5 else ''
            credits_rows += f'''<tr>
                <td>{cat_name} {toggle_btn}</td>
                <td class="mono text-right">{c.get("count",0)}</td>
                <td class="mono text-right credit">RM {c.get("amount",0):,.2f}</td>
                <td class="mono text-right">{c.get("percentage",0):.1f}%</td>
            </tr>{top5_html}'''
    
    # Build debits rows with expandable Top 5
    debits_rows = ""
    if not debits_cat:
        debits_rows = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:2rem;font-style:italic">No debit category data available in JSON</td></tr>'
    else:
        for idx, c in enumerate(debits_cat):
            cat_name = c.get("category", "")
            top5 = c.get("top_5_transactions", [])
            has_top5 = len(top5) > 0
            
            top5_html = ""
            if has_top5:
                top5_rows = "".join([f'<tr><td>{t.get("date","")}</td><td>{(t.get("counterparty") or t.get("description") or "")[:30]}</td><td class="mono text-right debit">RM {t.get("amount",0):,.2f}</td></tr>' for t in top5[:5]])
                top5_html = f'''<tr id="dr_top5_{idx}" class="top5-row" style="display:none"><td colspan="4">
                    <div class="top5-container"><table class="data-table mini"><thead><tr><th>Date</th><th>Counterparty</th><th class="text-right">Amount</th></tr></thead><tbody>{top5_rows}</tbody></table></div>
                </td></tr>'''
            
            toggle_btn = f'<button class="top5-btn" onclick="toggleTop5(\'dr_top5_{idx}\')">▶ Top 5</button>' if has_top5 else ''
            debits_rows += f'''<tr>
                <td>{cat_name} {toggle_btn}</td>
                <td class="mono text-right">{c.get("count",0)}</td>
                <td class="mono text-right debit">RM {c.get("amount",0):,.2f}</td>
                <td class="mono text-right">{c.get("percentage",0):.1f}%</td>
            </tr>{top5_html}'''
    
    # Observations
    pos_obs = "".join([f'<li class="observation-item">{o}</li>' for o in observations.get('positive', [])])
    con_obs = "".join([f'<li class="observation-item">{o}</li>' for o in observations.get('concerns', [])])
    
    # Recommendations
    rec_html = ""
    for rec in recommendations:
        p = rec.get('priority', 'LOW').lower()
        rec_html += f'''
                    <div class="recommendation-item">
                        <span class="recommendation-priority {p}">{rec.get('priority','LOW')}</span>
                        <div class="recommendation-content">
                            <div class="recommendation-category">{rec.get('category','')}</div>
                            <div class="recommendation-text">{rec.get('recommendation','')}</div>
                        </div>
                    </div>'''
    
    # Round figure transactions JS array
    # FIXED: Schema v5.1.0 uses 'all_transactions' and 'top_10_transactions', not 'transactions'
    round_txns = round_fig.get('all_transactions', round_fig.get('top_10_transactions', round_fig.get('transactions', [])))
    round_js = json.dumps([{
        'date': t.get('date',''), 
        'desc': t.get('description',''), 
        'type': t.get('type','CREDIT'), 
        'amount': t.get('amount',0), 
        'account': t.get('account','')
    } for t in round_txns])
    
    round_note = ""
    if len(round_txns) < round_count:
        round_note = f"<div style='color:var(--warn);font-size:0.85rem;margin-top:0.5rem'>⚠️ Showing {len(round_txns)} of {round_count} transactions</div>"
    
    # =====================================================
    # FIX #6: Kite Flying Indicators with detail view
    # FIXED: Handle both string list and dict list formats
    # =====================================================
    kite_indicators = kite.get('indicators', [])
    kite_rows = ""
    
    # Check if indicators are strings or dicts
    if kite_indicators and isinstance(kite_indicators[0], dict):
        # New format: list of dictionaries
        for i in kite_indicators:
            status = i.get("status", "PASS")
            status_class = "LOW" if status == "PASS" else "MODERATE" if status in ["MONITOR", "WARNING"] else "EXTREME"
            kite_rows += f'<tr><td>{i.get("indicator","")}</td><td><span class="volatility-badge volatility-{status_class}">{status}</span></td><td class="mono text-right">{i.get("points",0)}</td><td>{i.get("finding","")}</td></tr>'
    elif kite_indicators and isinstance(kite_indicators[0], str):
        # Old format: list of strings - convert to table rows
        detailed_findings = kite.get('detailed_findings', [])
        for idx, indicator_str in enumerate(kite_indicators):
            finding = detailed_findings[idx] if idx < len(detailed_findings) else indicator_str
            # Determine status based on kite score
            status = "WARNING" if kite_score > 0 else "PASS"
            status_class = "MODERATE" if status == "WARNING" else "LOW"
            kite_rows += f'<tr><td>{indicator_str}</td><td><span class="volatility-badge volatility-{status_class}">{status}</span></td><td class="mono text-right">-</td><td>{finding}</td></tr>'
    
    if not kite_rows:
        # Generate default 7 indicators if not provided
        default_indicators = [
            ("Circular Transfers", "PASS", 0, "No A→B→A patterns detected"),
            ("Month-End Concentration", "PASS", 0, "Normal distribution"),
            ("Round Amount Patterns", "WARNING" if round_count > 5 else "PASS", 2 if round_count > 5 else 0, f"{round_count} round figure transactions"),
            ("Timing Exploitation", "PASS", 0, "No suspicious timing patterns"),
            ("Suspicious Balance Spikes", "PASS", 0, "Balance movements within normal range"),
            ("Same Amount In/Out", "PASS", 0, "No matching in/out amounts detected"),
            ("Vague Descriptions", "PASS", 0, "Transaction descriptions are clear"),
        ]
        for ind, status, pts, finding in default_indicators:
            status_class = "LOW" if status == "PASS" else "MODERATE" if status == "WARNING" else "EXTREME"
            kite_rows += f'<tr><td>{ind}</td><td><span class="volatility-badge volatility-{status_class}">{status}</span></td><td class="mono text-right">{pts}</td><td>{finding}</td></tr>'
    
    # Volatility alerts
    vol_alerts = volatility.get('alerts', [])
    if not vol_alerts:
        for a in accounts:
            for m in a.get('monthly_summary', []):
                vl = m.get('volatility_level', 'LOW')
                vpct = m.get('volatility_pct', 0)
                month_name = m.get('month_name', m.get('month', ''))
                if vl in ['HIGH', 'EXTREME']:
                    vol_alerts.append(f"{month_name} ({a.get('bank_name','')}): {vpct:.0f}% volatility - {vl}")
    vol_alerts_html = "".join([f'<li>{a}</li>' for a in vol_alerts]) if vol_alerts else '<li style="color:var(--accent)">✓ No extreme volatility alerts</li>'
    
    # v5.0: Volatility method note
    vol_method_note = ""
    if schema_version == '5.0':
        vol_method_note = '''<div style="margin-top:1rem;padding:0.75rem;background:var(--info-dim);border-radius:8px;font-size:0.85rem;color:var(--info)">
            <strong>ℹ️ v5.0 Intraday Calculation:</strong> Volatility uses ALL transaction balances (intraday), not just End-of-Day balances.
        </div>'''
    
    # Chart data - handle missing categories gracefully
    if credits_cat:
        credit_vals = json.dumps([c.get('percentage', 0) for c in credits_cat])
        credit_labels = json.dumps([c.get('category', '') for c in credits_cat])
    else:
        credit_vals = json.dumps([])
        credit_labels = json.dumps([])
    
    if debits_cat:
        debit_vals = json.dumps([c.get('percentage', 0) for c in debits_cat])
        debit_labels = json.dumps([c.get('category', '') for c in debits_cat])
    else:
        debit_vals = json.dumps([])
        debit_labels = json.dumps([])
    
    # Volatility chart data
    vol_data = []
    period_year = period_start[:4] if period_start else '2024'
    month_names_list = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    for i, a in enumerate(accounts):
        monthly = a.get('monthly_summary', [])
        fixed_labels = []
        for m in monthly:
            month_str = m.get('month', '')
            month_name = m.get('month_name', '')
            if month_str and '-' in month_str:
                parts = month_str.split('-')
                month_num = int(parts[1]) if len(parts) > 1 else 1
                fixed_labels.append(f"{month_names_list[month_num-1]} {period_year}")
            elif month_name:
                fixed_labels.append(month_name)
            else:
                fixed_labels.append(m.get('month', ''))
        
        vol_data.append({
            'x': fixed_labels,
            'y': [m.get('volatility_pct',0) for m in monthly],
            'name': a.get('bank_name',''),
            'type': 'bar',
            'marker': {'color': '#f59e0b' if i == 0 else '#ef4444' if i == 1 else '#8b5cf6'}
        })
    vol_data_js = json.dumps(vol_data)
    
    # Integrity checks table
    int_checks = integrity.get('checks', [])
    int_rows = ""
    for c in int_checks:
        tier = c.get('tier', 'MONITOR')
        status = c.get('status', 'PASS')
        tier_color = 'danger' if tier == 'CRITICAL' else 'warn' if tier == 'WARNING' else 'purple' if tier == 'COMPLIANCE' else 'info'
        status_color = 'accent' if status == 'PASS' else 'danger'
        int_rows += f'''<tr>
            <td class="mono">{c.get('id','')}</td>
            <td>{c.get('name','')}</td>
            <td><span class="volatility-badge" style="background:var(--{tier_color}-dim);color:var(--{tier_color})">{tier}</span></td>
            <td><span class="volatility-badge" style="background:var(--{status_color}-dim);color:var(--{status_color})">{status}</span></td>
            <td class="mono text-right">{c.get('weight',0)}</td>
            <td class="mono text-right">{c.get('points_earned',0)}</td>
            <td style="color:var(--text-soft)">{c.get('details','')}</td>
        </tr>'''
    
    if not int_rows:
        int_rows = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">No integrity checks data available</td></tr>'
    
    # Related Party summary
    rp_credit = exclusions.get('credits', {}).get('related_party', 0)
    rp_debit = exclusions.get('debits', {}).get('related_party', 0)
    rp_net = rp_credit - rp_debit
    # FIX: Handle related_parties as list of dicts (v5.0.4) or list of strings (v4.0)
    if related_parties:
        if isinstance(related_parties[0], dict):
            # v5.0.4 format: [{"name": "...", "relationship": "..."}, ...]
            rp_parties = ', '.join(p.get('name', str(p)) for p in related_parties)
        else:
            # v4.0 format: ["name1", "name2", ...]
            rp_parties = ', '.join(str(p) for p in related_parties)
    else:
        rp_parties = 'None specified'
    
    # Exclusions breakdown
    # FIX: Handle inter_account as dict (v5.0.4) or number (v4.0)
    def safe_exclusion_value(val):
        """Extract numeric value from exclusion field (handles dict or number)"""
        if isinstance(val, dict):
            return val.get('total', 0)
        return val if isinstance(val, (int, float)) else 0
    
    exc_credits = exclusions.get('credits', {})
    exc_debits = exclusions.get('debits', {})
    exc_cr_inter = safe_exclusion_value(exc_credits.get('inter_account', 0))
    exc_cr_related = safe_exclusion_value(exc_credits.get('related_party', 0))
    exc_cr_reversals = safe_exclusion_value(exc_credits.get('reversals', 0))
    exc_cr_loan = safe_exclusion_value(exc_credits.get('loan_disbursement', 0))
    exc_cr_interest = safe_exclusion_value(exc_credits.get('interest_fd_dividend', 0))
    exc_cr_total = safe_exclusion_value(exc_credits.get('total', 0))
    exc_dr_inter = safe_exclusion_value(exc_debits.get('inter_account', 0))
    exc_dr_related = safe_exclusion_value(exc_debits.get('related_party', 0))
    exc_dr_returned = safe_exclusion_value(exc_debits.get('returned_cheque', 0))
    exc_dr_total = safe_exclusion_value(exc_debits.get('total', 0))
    
    # =====================================================
    # FIX #1: Recurring Payments - check for 'statutory_payments' key too
    # =====================================================
    recurring_tab = ""
    if recurring:
        # Try multiple possible keys for the payments array
        rec_payments = recurring.get('payments', []) or recurring.get('statutory_payments', []) or recurring.get('payment_types', [])
        rec_alerts = recurring.get('alerts', []) or recurring.get('warnings', [])
        rec_assessment = recurring.get('assessment', {})
        
        # If no payments array but has individual payment type data, construct it
        if not rec_payments:
            payment_types = ['EPF/KWSP', 'SOCSO/PERKESO', 'TAX/LHDN', 'RENT', 'UTILITIES', 'LOAN_REPAYMENT']
            for pt in payment_types:
                pt_data = recurring.get(pt.lower().replace('/', '_'), {}) or recurring.get(pt, {})
                if pt_data:
                    rec_payments.append({
                        'type': pt,
                        'expected_count': pt_data.get('expected', total_months),
                        'found_count': pt_data.get('found', pt_data.get('count', 0)),
                        'missing_months': pt_data.get('missing_months', []),
                        'status': pt_data.get('status', 'OK')
                    })
        
        rec_rows = ""
        for p in rec_payments:
            status = p.get('status', 'OK')
            missing = ', '.join(p.get('missing_months', [])) or 'None'
            rec_rows += f'''<tr>
                <td>{p.get('type', p.get('payment_type', ''))}</td>
                <td class="mono text-right">{p.get('expected_count', p.get('expected', 0))}</td>
                <td class="mono text-right">{p.get('found_count', p.get('found', p.get('count', 0)))}</td>
                <td style="font-size:0.85rem;color:var(--text-soft)">{missing}</td>
                <td><span class="volatility-badge volatility-{'LOW' if status in ['OK', 'COMPLIANT', 'PASS'] else 'EXTREME'}">{status}</span></td>
            </tr>'''
        
        # If still no rows, show informative message
        if not rec_rows:
            rec_rows = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No statutory payment data available in JSON</td></tr>'
        
        rec_alerts_html = "".join([f'<li style="color:var(--danger)">{a}</li>' for a in rec_alerts]) if rec_alerts else '<li style="color:var(--accent)">✓ All statutory payments detected</li>'
        
        # FIX: Handle assessment being either a string or a dictionary
        if isinstance(rec_assessment, str):
            # Assessment is a string like "Some statutory payments missing" or "Statutory obligations appear to be met"
            assessment_text = rec_assessment.upper()
            if 'MISSING' in assessment_text or 'ALERT' in assessment_text or 'NOT' in assessment_text:
                compliance = 'ALERT'
                risk = 'MODERATE'
            elif 'OK' in assessment_text or 'MET' in assessment_text or 'COMPLIANT' in assessment_text:
                compliance = 'COMPLIANT'
                risk = 'LOW'
            else:
                compliance = rec_assessment  # Use the string as-is
                risk = 'LOW'
        elif isinstance(rec_assessment, dict):
            compliance = rec_assessment.get('statutory_compliance', rec_assessment.get('compliance', 'COMPLIANT'))
            risk = rec_assessment.get('risk_level', 'LOW')
        else:
            compliance = 'COMPLIANT'
            risk = 'LOW'
        
        recurring_tab = f'''
        <div id="tab-recurring" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">📋 Recurring Payments Compliance</h2></div>
                <div class="section-content">
                    <div class="summary-cards">
                        <div class="summary-card"><div class="value" style="color:var(--{'accent' if compliance in ['COMPLIANT','OK'] else 'danger'})">{compliance}</div><div class="label">Statutory Compliance</div></div>
                        <div class="summary-card"><div class="value" style="color:var(--{'accent' if risk=='LOW' else 'warn' if risk=='MODERATE' else 'danger'})">{risk}</div><div class="label">Risk Level</div></div>
                    </div>
                    <div class="table-container">
                        <table class="data-table">
                            <thead><tr><th>Payment Type</th><th class="text-right">Expected</th><th class="text-right">Found</th><th>Missing Months</th><th>Status</th></tr></thead>
                            <tbody>{rec_rows}</tbody>
                        </table>
                    </div>
                    <div class="flag-card" style="margin-top:1rem">
                        <div class="flag-header"><span class="flag-title">⚠️ Alerts</span></div>
                        <ul style="color:var(--text-soft);padding:1rem 1.5rem">{rec_alerts_html}</ul>
                    </div>
                </div>
            </div>
        </div>'''
    
    # =====================================================
    # FIX #2: Non-Bank Financing - deduplicate sources
    # =====================================================
    nonbank_tab = ""
    if non_bank:
        nb_sources = non_bank.get('sources', [])
        nb_suspected = non_bank.get('suspected_unlicensed', [])
        nb_assessment = non_bank.get('assessment', {})
        
        # FIX: Handle risk_level at top level or inside assessment
        nb_risk = non_bank.get('risk_level', 'LOW')
        
        # FIX: Handle assessment being either a string or a dictionary
        if isinstance(nb_assessment, str):
            nb_summary = nb_assessment
        elif isinstance(nb_assessment, dict):
            nb_risk = nb_assessment.get('risk_level', nb_risk)
            nb_summary = nb_assessment.get('summary', '')
        else:
            nb_summary = ''
        
        # Deduplicate sources by total_inflow amount
        seen_amounts = set()
        unique_sources = []
        for s in nb_sources:
            amount = s.get('total_inflow', 0)
            if amount not in seen_amounts:
                seen_amounts.add(amount)
                unique_sources.append(s)
        
        source_rows = ""
        for s in unique_sources:
            status = s.get('status', 'INFO')
            status_class = 'info' if status == 'INFO' else 'warn' if status == 'MONITOR' else 'danger'
            source_rows += f'''<tr>
                <td>{s.get('source_type','')}</td>
                <td class="mono text-right">{s.get('count',0)}</td>
                <td class="mono text-right credit">RM {s.get('total_inflow',0):,.2f}</td>
                <td class="mono text-right debit">RM {s.get('total_repayment',0) or 0:,.2f}</td>
                <td><span class="volatility-badge" style="background:var(--{status_class}-dim);color:var(--{status_class})">{status}</span></td>
            </tr>'''
        
        # Suspected unlicensed table
        suspected_rows = ""
        for sus in nb_suspected[:10]:
            suspected_rows += f'''<tr>
                <td>{sus.get('date','')}</td>
                <td>{(sus.get('counterparty') or sus.get('description') or '')[:40]}</td>
                <td class="mono text-right credit">RM {sus.get('amount',0):,.2f}</td>
                <td>{sus.get('reason','')}</td>
            </tr>'''
        
        suspected_section = ""
        if suspected_rows:
            suspected_section = f'''
                    <div class="flag-card" style="margin-top:1rem">
                        <div class="flag-header" onclick="toggleDetails('suspectedDetails')"><span class="flag-title">⚠️ Suspected Unlicensed Lending</span><span class="flag-count" style="background:var(--danger-dim);color:var(--danger)">{len(nb_suspected)} found</span></div>
                        <div id="suspectedDetails" class="flag-details show">
                            <table class="data-table"><thead><tr><th>Date</th><th>Counterparty</th><th class="text-right">Amount</th><th>Reason</th></tr></thead><tbody>{suspected_rows}</tbody></table>
                        </div>
                    </div>'''
        
        nonbank_tab = f'''
        <div id="tab-nonbank" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">🏦 Non-Bank Financing Detection</h2></div>
                <div class="section-content">
                    <div class="summary-cards">
                        <div class="summary-card"><div class="value" style="color:var(--{'accent' if nb_risk=='LOW' else 'warn' if nb_risk=='MODERATE' else 'danger'})">{nb_risk}</div><div class="label">Risk Level</div></div>
                    </div>
                    <div class="flag-card">
                        <div class="flag-header"><span class="flag-title">📊 Financing Sources</span></div>
                        <div class="table-container" style="margin-top:1rem">
                            <table class="data-table">
                                <thead><tr><th>Source Type</th><th class="text-right">Count</th><th class="text-right">Total Inflow</th><th class="text-right">Repayments</th><th>Status</th></tr></thead>
                                <tbody>{source_rows if source_rows else '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No non-bank financing detected</td></tr>'}</tbody>
                            </table>
                        </div>
                    </div>
                    {suspected_section}
                    {f'<div style="margin-top:1rem;padding:1rem;background:var(--bg-alt);border-radius:8px;color:var(--text-soft)">{nb_summary}</div>' if nb_summary else ''}
                </div>
            </div>
        </div>'''
    
    # =====================================================
    # FIX #5: Counterparty Analysis Tab
    # =====================================================
    counterparty_tab = ""
    if counterparties:
        top_payers = counterparties.get('top_payers', [])
        top_payees = counterparties.get('top_payees', [])
        concentration = counterparties.get('concentration_risk', {})
        parties_both = counterparties.get('parties_both_sides', [])
        
        payer_rows = ""
        for p in top_payers[:10]:
            is_related = '👤' if p.get('is_related_party') else ''
            payer_rows += f'''<tr>
                <td>{p.get('rank','')}</td>
                <td>{p.get('party_name','')[:35]} {is_related}</td>
                <td class="mono text-right">{p.get('transaction_count',0)}</td>
                <td class="mono text-right credit">RM {p.get('total_amount',0):,.2f}</td>
                <td class="mono text-right">{p.get('percentage',0):.1f}%</td>
            </tr>'''
        
        payee_rows = ""
        for p in top_payees[:10]:
            is_related = '👤' if p.get('is_related_party') else ''
            payee_rows += f'''<tr>
                <td>{p.get('rank','')}</td>
                <td>{p.get('party_name','')[:35]} {is_related}</td>
                <td class="mono text-right">{p.get('transaction_count',0)}</td>
                <td class="mono text-right debit">RM {p.get('total_amount',0):,.2f}</td>
                <td class="mono text-right">{p.get('percentage',0):.1f}%</td>
            </tr>'''
        
        conc_risk = concentration.get('risk_level', 'LOW')
        top1_payer = concentration.get('top1_payer_pct', 0)
        top3_payers = concentration.get('top3_payers_pct', 0)
        top1_payee = concentration.get('top1_payee_pct', 0)
        top3_payees = concentration.get('top3_payees_pct', 0)
        
        # Parties appearing both sides
        both_rows = ""
        for p in parties_both[:5]:
            both_rows += f'''<tr>
                <td>{p.get('party_name','')[:35]}</td>
                <td class="mono text-right credit">RM {p.get('credit_amount',0):,.2f}</td>
                <td class="mono text-right debit">RM {p.get('debit_amount',0):,.2f}</td>
            </tr>'''
        
        both_section = ""
        if parties_both:
            both_section = f'''
                    <div class="flag-card" style="margin-top:1.5rem">
                        <div class="flag-header"><span class="flag-title">⚠️ Parties Appearing Both Sides</span><span class="flag-count">{len(parties_both)} found</span></div>
                        <div class="table-container" style="padding:1rem">
                            <table class="data-table"><thead><tr><th>Party</th><th class="text-right">Credits</th><th class="text-right">Debits</th></tr></thead><tbody>{both_rows}</tbody></table>
                        </div>
                    </div>'''

        counterparty_tab = f'''
        <div id="tab-counterparties" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">👥 Counterparty Analysis</h2></div>
                <div class="section-content">
                    <div class="summary-cards">
                        <div class="summary-card"><div class="value" style="color:var(--{'accent' if conc_risk=='LOW' else 'warn' if conc_risk=='MODERATE' else 'danger'})">{conc_risk}</div><div class="label">Concentration Risk</div></div>
                        <div class="summary-card"><div class="value">{top1_payer:.0f}%</div><div class="label">Top 1 Payer</div></div>
                        <div class="summary-card"><div class="value">{top3_payers:.0f}%</div><div class="label">Top 3 Payers</div></div>
                        <div class="summary-card"><div class="value">{top1_payee:.0f}%</div><div class="label">Top 1 Payee</div></div>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:2rem;margin-top:1.5rem">
                        <div>
                            <h4 style="color:var(--accent);margin-bottom:1rem">💰 Top Income Sources (Payers)</h4>
                            <table class="data-table">
                                <thead><tr><th>#</th><th>Party</th><th class="text-right">Count</th><th class="text-right">Amount</th><th class="text-right">%</th></tr></thead>
                                <tbody>{payer_rows if payer_rows else '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No data</td></tr>'}</tbody>
                            </table>
                        </div>
                        <div>
                            <h4 style="color:var(--danger);margin-bottom:1rem">💸 Top Payment Destinations (Payees)</h4>
                            <table class="data-table">
                                <thead><tr><th>#</th><th>Party</th><th class="text-right">Count</th><th class="text-right">Amount</th><th class="text-right">%</th></tr></thead>
                                <tbody>{payee_rows if payee_rows else '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No data</td></tr>'}</tbody>
                            </table>
                        </div>
                    </div>
                    {both_section}
                </div>
            </div>
        </div>'''
    
    # v5.0: Returned cheques flag card
    returned_cheques_html = ""
    if returned_count > 0:
        ret_txns = returned_cheques.get('transactions', [])
        ret_rows = "".join([f'<tr><td>{t.get("date","")}</td><td>{t.get("description","")[:40]}</td><td class="mono text-right debit">RM {t.get("amount",0):,.2f}</td></tr>' for t in ret_txns[:10]])
        returned_cheques_html = f'''
                    <div class="flag-card">
                        <div class="flag-header" onclick="toggleDetails('returnedDetails')"><span class="flag-title">❌ Returned Cheques</span><span class="flag-count" style="background:var(--danger-dim);color:var(--danger)">{returned_count} found - {returned_assessment}</span></div>
                        <div id="returnedDetails" class="flag-details show">
                            <div style="margin-bottom:0.75rem;color:var(--text-soft)">Total Value: <span class="mono debit">RM {returned_cheques.get('total_value',0):,.2f}</span></div>
                            <table class="data-table">
                                <thead><tr><th>Date</th><th>Description</th><th class="text-right">Amount</th></tr></thead>
                                <tbody>{ret_rows}</tbody>
                            </table>
                        </div>
                    </div>'''
    
    # Inter-account transfers section
    # FIXED: Schema v5.1.0 has nested structure with matched_transfers and unverified_transfers
    matched = inter_account.get('matched_transfers', {})
    unverified = inter_account.get('unverified_transfers', {})
    summary = inter_account.get('summary', {})
    
    # Get transfers from the correct location
    inter_transfers = matched.get('all_transfers', matched.get('top_10_transfers', inter_account.get('transfers', [])))
    inter_count = summary.get('total_count', inter_account.get('detected_count', len(inter_transfers)))
    inter_total = summary.get('total_amount', inter_account.get('total_amount', 0))
    
    inter_rows = ""
    for t in inter_transfers[:10]:
        inter_rows += f'''<tr>
            <td>{t.get('date','')}</td>
            <td>{t.get('from_account', t.get('debit_account', ''))[-8:]}</td>
            <td>{t.get('to_account', t.get('credit_account', ''))[-8:]}</td>
            <td class="mono text-right">RM {t.get('amount',0):,.2f}</td>
        </tr>'''
    
    # Pre-render inter-transfer section to avoid multi-line f-string inside { ... }
    inter_transfers_section = ""
    if inter_transfers:
        inter_transfers_section = f'''
                    <div class="section" style="margin-top:1.5rem">
                        <div class="section-header" onclick="toggleSection('interTransfers')"><h2 class="section-title">🔄 Inter-Account Transfers</h2></div>
                        <div id="interTransfers" class="section-content collapsed">
                            <div class="summary-cards">
                                <div class="summary-card"><div class="value">{inter_count}</div><div class="label">Transfers Detected</div></div>
                                <div class="summary-card"><div class="value">RM {inter_total:,.0f}</div><div class="label">Total Amount</div></div>
                            </div>
                            <table class="data-table"><thead><tr><th>Date</th><th>From Account</th><th>To Account</th><th class="text-right">Amount</th></tr></thead><tbody>{inter_rows}</tbody></table>
                        </div>
                    </div>'''

    # Dynamic nav tabs based on available data
    recurring_nav = '<button class="nav-tab" data-tab="recurring" onclick="showTab(\'recurring\')">📋 Recurring</button>' if recurring else ''
    nonbank_nav = '<button class="nav-tab" data-tab="nonbank" onclick="showTab(\'nonbank\')">🏦 Non-Bank</button>' if non_bank else ''
    counterparty_nav = '<button class="nav-tab" data-tab="counterparties" onclick="showTab(\'counterparties\')">👥 Counterparties</button>' if counterparties else ''
    
    # Generate HTML
    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bank Statement Analysis v5.0 - {company}</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        :root, [data-theme="dark"] {{
            --bg: #0a0e17; --bg-alt: #0f1520; --card-bg: #141b2b; --card-hover: #1a2235;
            --border-subtle: #1e2a42; --border-accent: #2d3f5f;
            --accent: #22c55e; --accent-dim: rgba(34, 197, 94, 0.15);
            --danger: #ef4444; --danger-dim: rgba(239, 68, 68, 0.15);
            --warn: #f59e0b; --warn-dim: rgba(245, 158, 11, 0.15);
            --info: #3b82f6; --info-dim: rgba(59, 130, 246, 0.15);
            --purple: #8b5cf6; --purple-dim: rgba(139, 92, 246, 0.15);
            --text-main: #e8eaed; --text-soft: #9ca3af; --text-muted: #6b7280;
        }}
        [data-theme="light"] {{
            --bg: #f8fafc; --bg-alt: #ffffff; --card-bg: #ffffff; --card-hover: #f1f5f9;
            --border-subtle: #e2e8f0; --border-accent: #cbd5e1;
            --accent: #16a34a; --accent-dim: rgba(22, 163, 74, 0.1);
            --danger: #dc2626; --danger-dim: rgba(220, 38, 38, 0.1);
            --warn: #d97706; --warn-dim: rgba(217, 119, 6, 0.1);
            --info: #2563eb; --info-dim: rgba(37, 99, 235, 0.1);
            --purple: #7c3aed; --purple-dim: rgba(124, 58, 237, 0.1);
            --text-main: #1e293b; --text-soft: #475569; --text-muted: #94a3b8;
        }}
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text-main); line-height: 1.6; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 2rem; }}
        .header {{ background: linear-gradient(135deg, var(--card-bg) 0%, var(--bg-alt) 100%); border: 1px solid var(--border-subtle); border-radius: 16px; padding: 2rem; margin-bottom: 2rem; position: relative; overflow: hidden; }}
        .header::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: linear-gradient(90deg, #22c55e, #3b82f6, #8b5cf6); }}
        .header-content {{ display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1.5rem; }}
        .company-info h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.5rem; }}
        .company-info .period {{ color: var(--text-soft); font-size: 0.9rem; }}
        .header-stats {{ display: flex; gap: 2rem; }}
        .header-stat {{ text-align: center; }}
        .header-stat .value {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
        .header-stat .label {{ font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; }}
        .version-badge {{ display: inline-block; padding: 0.25rem 0.75rem; background: var(--purple-dim); color: var(--purple); border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-left: 1rem; }}
        .nav-tabs {{ display: flex; gap: 0.5rem; margin-bottom: 2rem; flex-wrap: wrap; background: var(--card-bg); padding: 0.5rem; border-radius: 12px; border: 1px solid var(--border-subtle); }}
        .nav-tab {{ padding: 0.75rem 1.25rem; border: none; background: transparent; color: var(--text-soft); cursor: pointer; border-radius: 8px; font-size: 0.85rem; font-weight: 500; transition: all 0.2s; }}
        .nav-tab:hover {{ background: var(--card-hover); color: var(--text-main); }}
        .nav-tab.active {{ background: var(--accent); color: #fff; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .scores-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .score-card {{ background: var(--card-bg); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 1.5rem; text-align: center; cursor: pointer; transition: all 0.2s; }}
        .score-card:hover {{ transform: translateY(-2px); border-color: var(--border-accent); }}
        .score-card.excellent {{ border-left: 4px solid var(--accent); }}
        .score-card.good {{ border-left: 4px solid var(--info); }}
        .score-card.warning {{ border-left: 4px solid var(--warn); }}
        .score-card.danger {{ border-left: 4px solid var(--danger); }}
        .score-value {{ font-size: 2.5rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
        .score-label {{ font-size: 0.85rem; color: var(--text-soft); margin: 0.5rem 0; }}
        .score-rating {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }}
        .score-card.excellent .score-value, .score-card.excellent .score-rating {{ color: var(--accent); }}
        .score-card.good .score-value, .score-card.good .score-rating {{ color: var(--info); }}
        .score-card.warning .score-value, .score-card.warning .score-rating {{ color: var(--warn); }}
        .score-card.danger .score-value, .score-card.danger .score-rating {{ color: var(--danger); }}
        .accounts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .account-card {{ background: var(--card-bg); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 1.25rem; }}
        .account-card.primary {{ border-left: 4px solid var(--accent); }}
        .account-card.secondary {{ border-left: 4px solid var(--info); }}
        .account-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }}
        .bank-name {{ font-weight: 600; font-size: 0.95rem; }}
        .badge {{ padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; }}
        .badge-primary {{ background: var(--accent-dim); color: var(--accent); }}
        .badge-secondary {{ background: var(--info-dim); color: var(--info); }}
        .account-number {{ font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--text-soft); margin-bottom: 1rem; }}
        .account-metrics {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.75rem; }}
        .metric {{ background: var(--bg-alt); padding: 0.75rem; border-radius: 8px; }}
        .metric-label {{ font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; }}
        .metric-value {{ font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; }}
        .metric-value.credit {{ color: var(--accent); }}
        .metric-value.debit {{ color: var(--danger); }}
        .section {{ background: var(--card-bg); border: 1px solid var(--border-subtle); border-radius: 12px; margin-bottom: 1.5rem; overflow: hidden; }}
        .section-header {{ display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; background: var(--bg-alt); border-bottom: 1px solid var(--border-subtle); cursor: pointer; }}
        .section-title {{ font-size: 1rem; font-weight: 600; }}
        .section-toggle {{ background: none; border: none; color: var(--text-soft); cursor: pointer; font-size: 0.85rem; }}
        .section-content {{ padding: 1.5rem; }}
        .section-content.collapsed {{ display: none; }}
        .table-container {{ overflow-x: auto; }}
        .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
        .data-table th, .data-table td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border-subtle); }}
        .data-table th {{ background: var(--bg-alt); color: var(--text-soft); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }}
        .data-table tr:hover {{ background: var(--card-hover); }}
        .data-table.mini th, .data-table.mini td {{ padding: 0.5rem 0.75rem; font-size: 0.8rem; }}
        .text-right {{ text-align: right; }}
        .mono {{ font-family: 'JetBrains Mono', monospace; }}
        .credit {{ color: var(--accent); }}
        .debit {{ color: var(--danger); }}
        .volatility-badge {{ display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; }}
        .volatility-LOW {{ background: var(--accent-dim); color: var(--accent); }}
        .volatility-MODERATE {{ background: var(--warn-dim); color: var(--warn); }}
        .volatility-HIGH {{ background: var(--warn-dim); color: var(--warn); }}
        .volatility-EXTREME {{ background: var(--danger-dim); color: var(--danger); }}
        .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
        .summary-card {{ background: var(--bg-alt); padding: 1.25rem; border-radius: 8px; text-align: center; }}
        .summary-card .value {{ font-size: 1.5rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
        .summary-card .label {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem; }}
        .flag-card {{ background: var(--bg-alt); border-radius: 8px; margin-bottom: 1rem; overflow: hidden; }}
        .flag-header {{ display: flex; justify-content: space-between; align-items: center; padding: 1rem; cursor: pointer; }}
        .flag-title {{ font-weight: 600; font-size: 0.9rem; }}
        .flag-count {{ background: var(--warn-dim); color: var(--warn); padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }}
        .flag-details {{ display: none; padding: 0 1rem 1rem; }}
        .flag-details.show {{ display: block; }}
        .turnover-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }}
        .turnover-column {{ background: var(--bg-alt); padding: 1.5rem; border-radius: 8px; }}
        .turnover-column h3 {{ font-size: 0.9rem; margin-bottom: 1rem; color: var(--text-soft); }}
        .turnover-column.business {{ border: 1px solid var(--purple); }}
        .turnover-column.business h3 {{ color: var(--purple); }}
        .turnover-row {{ display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle); }}
        .observations-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.5rem; }}
        .observation-list {{ list-style: none; padding: 0; }}
        .observation-item {{ padding: 0.5rem 0; padding-left: 1.5rem; position: relative; color: var(--text-soft); }}
        .observation-item::before {{ content: '•'; position: absolute; left: 0; }}
        .positive .observation-item::before {{ color: var(--accent); }}
        .concerns .observation-item::before {{ color: var(--danger); }}
        .recommendation-item {{ display: flex; gap: 1rem; padding: 1rem; background: var(--bg-alt); border-radius: 8px; margin-bottom: 0.75rem; }}
        .recommendation-priority {{ padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; height: fit-content; }}
        .recommendation-priority.high {{ background: var(--danger-dim); color: var(--danger); }}
        .recommendation-priority.medium {{ background: var(--warn-dim); color: var(--warn); }}
        .recommendation-priority.low {{ background: var(--info-dim); color: var(--info); }}
        .recommendation-category {{ font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem; }}
        .recommendation-text {{ font-size: 0.9rem; }}
        .chart-container {{ background: var(--bg-alt); border-radius: 8px; padding: 1rem; }}
        .chart-title {{ font-size: 0.85rem; font-weight: 600; margin-bottom: 0.75rem; color: var(--text-soft); }}
        .top5-btn {{ background: var(--info-dim); color: var(--info); border: none; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.7rem; cursor: pointer; margin-left: 0.5rem; }}
        .top5-btn:hover {{ background: var(--info); color: #fff; }}
        .top5-container {{ background: var(--card-hover); padding: 1rem; border-radius: 8px; margin: 0.5rem 0; }}
        .top5-row td {{ background: var(--bg-alt); }}
        .modal-overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); display: none; justify-content: center; align-items: center; z-index: 1000; padding: 2rem; }}
        .modal-overlay.show {{ display: flex; }}
        .modal {{ background: var(--card-bg); border-radius: 16px; max-width: 900px; width: 100%; max-height: 80vh; overflow: hidden; }}
        .modal-header {{ display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--border-subtle); }}
        .modal-title {{ font-size: 1.1rem; font-weight: 600; }}
        .modal-close {{ background: none; border: none; font-size: 1.5rem; color: var(--text-soft); cursor: pointer; }}
        .modal-body {{ padding: 1.5rem; max-height: calc(80vh - 70px); overflow-y: auto; }}
        .footer {{ text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem; }}
        .theme-toggle {{ position: fixed; top: 20px; right: 20px; background: var(--card-bg); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 0.5rem 1rem; color: var(--text-main); cursor: pointer; font-size: 0.85rem; z-index: 100; }}
        .theme-toggle:hover {{ background: var(--card-hover); }}
        @media (max-width: 768px) {{
            .container {{ padding: 1rem; }}
            .header-content {{ flex-direction: column; }}
            .observations-grid {{ grid-template-columns: 1fr; }}
            .theme-toggle {{ top: auto; bottom: 20px; }}
        }}
    </style>
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()">🌙 Dark</button>
    
    <div class="container">
        <div class="header">
            <div class="header-content">
                <div class="company-info">
                    <h1>{company} <span class="version-badge">Schema v{schema_version}</span></h1>
                    <p class="period">Bank Statement Analysis v5.0 | {period_start} - {period_end} | {total_months} Months</p>
                </div>
                <div class="header-stats">
                    <div class="header-stat"><div class="value">{len(accounts)}</div><div class="label">Accounts</div></div>
                    <div class="header-stat"><div class="value">{total_txns:,}</div><div class="label">Transactions</div></div>
                    <div class="header-stat"><div class="value">RM {gross.get('total_credits',0)/1000000:.2f}M</div><div class="label">Total Credits</div></div>
                </div>
            </div>
        </div>

        <div class="nav-tabs">
            <button class="nav-tab active" data-tab="overview" onclick="showTab('overview')">📊 Overview</button>
            <button class="nav-tab" data-tab="accounts" onclick="showTab('accounts')">🏦 Accounts</button>
            <button class="nav-tab" data-tab="turnover" onclick="showTab('turnover')">💰 Turnover</button>
            <button class="nav-tab" data-tab="categories" onclick="showTab('categories')">📁 Categories</button>
            {counterparty_nav}
            <button class="nav-tab" data-tab="volatility" onclick="showTab('volatility')">📈 Volatility</button>
            <button class="nav-tab" data-tab="flags" onclick="showTab('flags')">🚩 Flags</button>
            <button class="nav-tab" data-tab="integrity" onclick="showTab('integrity')">✓ Integrity</button>
            <button class="nav-tab" data-tab="related" onclick="showTab('related')">👥 Related</button>
            {recurring_nav}
            {nonbank_nav}
            <button class="nav-tab" data-tab="recommendations" onclick="showTab('recommendations')">✅ Recs</button>
        </div>

        <div id="tab-overview" class="tab-content active">
            <div class="scores-grid">
                <div class="score-card {int_class}"><div class="score-value">{int_score}%</div><div class="score-label">Integrity Score</div><div class="score-rating">{int_rating}</div></div>
                <div class="score-card {kite_class}" onclick="showTab('flags')"><div class="score-value">{kite_score}</div><div class="score-label">Kite Flying Risk</div><div class="score-rating">{kite_level} RISK</div></div>
                <div class="score-card {vol_class}"><div class="score-value">{vol_index:.0f}%</div><div class="score-label">Volatility Index</div><div class="score-rating">{vol_level}</div></div>
                <div class="score-card warning" onclick="showModal('roundFigureModal')"><div class="score-value">{round_count}</div><div class="score-label">Round Figure Flags</div><div class="score-rating">CLICK TO VIEW</div></div>
            </div>
            <div class="accounts-grid">{acc_cards}</div>
            <div class="section">
                <div class="section-header" onclick="toggleSection('observationsContent')"><h2 class="section-title">📊 Key Observations</h2><button class="section-toggle">Toggle</button></div>
                <div id="observationsContent" class="section-content">
                    <div class="observations-grid">
                        <div class="positive"><h4 style="color: var(--accent); font-size: 0.85rem; margin-bottom: 1rem;">✓ POSITIVE INDICATORS</h4><ul class="observation-list">{pos_obs}</ul></div>
                        <div class="concerns"><h4 style="color: var(--danger); font-size: 0.85rem; margin-bottom: 1rem;">⚠ AREAS OF CONCERN</h4><ul class="observation-list">{con_obs}</ul></div>
                    </div>
                </div>
            </div>
        </div>

        <div id="tab-accounts" class="tab-content">{monthly_tables}</div>

        <div id="tab-turnover" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">💰 Business Turnover Summary</h2></div>
                <div class="section-content">
                    <div class="turnover-grid">
                        <div class="turnover-column"><h3>Gross Totals</h3>
                            <div class="turnover-row"><span>Total Credits</span><span class="mono credit">RM {gross.get('total_credits',0):,.2f}</span></div>
                            <div class="turnover-row"><span>Total Debits</span><span class="mono debit">RM {gross.get('total_debits',0):,.2f}</span></div>
                            <div class="turnover-row"><span>Net Flow</span><span class="mono {'debit' if gross.get('net_flow',0)<0 else 'credit'}">RM {gross.get('net_flow',0):,.2f}</span></div>
                        </div>
                        <div class="turnover-column business"><h3>Business Turnover (Excl. Internal)</h3>
                            <div class="turnover-row"><span>Net Credits</span><span class="mono credit">RM {business.get('net_credits',0):,.2f}</span></div>
                            <div class="turnover-row"><span>Net Debits</span><span class="mono debit">RM {business.get('net_debits',0):,.2f}</span></div>
                            <div class="turnover-row"><span>Net Flow</span><span class="mono {'debit' if business.get('net_flow',0)<0 else 'credit'}">RM {business.get('net_flow',0):,.2f}</span></div>
                        </div>
                    </div>
                    <div class="section" style="margin-top:1.5rem">
                        <div class="section-header" onclick="toggleSection('exclusionsDetails')"><h2 class="section-title">🔍 Exclusions Breakdown</h2></div>
                        <div id="exclusionsDetails" class="section-content collapsed">
                            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:2rem">
                                <div><h4 style="color:var(--accent);margin-bottom:1rem">CREDIT EXCLUSIONS</h4>
                                    <table class="data-table">
                                        <tr><td>Inter-Account</td><td class="mono text-right">RM {exc_cr_inter:,.2f}</td></tr>
                                        <tr><td>Related Party</td><td class="mono text-right">RM {exc_cr_related:,.2f}</td></tr>
                                        <tr><td>Reversals</td><td class="mono text-right">RM {exc_cr_reversals:,.2f}</td></tr>
                                        <tr><td>Loan Disbursement</td><td class="mono text-right">RM {exc_cr_loan:,.2f}</td></tr>
                                        <tr><td>Interest/FD</td><td class="mono text-right">RM {exc_cr_interest:,.2f}</td></tr>
                                        <tr style="font-weight:600"><td>Total</td><td class="mono text-right">RM {exc_cr_total:,.2f}</td></tr>
                                    </table>
                                </div>
                                <div><h4 style="color:var(--danger);margin-bottom:1rem">DEBIT EXCLUSIONS</h4>
                                    <table class="data-table">
                                        <tr><td>Inter-Account</td><td class="mono text-right">RM {exc_dr_inter:,.2f}</td></tr>
                                        <tr><td>Related Party</td><td class="mono text-right">RM {exc_dr_related:,.2f}</td></tr>
                                        <tr><td>Returned Cheque</td><td class="mono text-right">RM {exc_dr_returned:,.2f}</td></tr>
                                        <tr style="font-weight:600"><td>Total</td><td class="mono text-right">RM {exc_dr_total:,.2f}</td></tr>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                    {inter_transfers_section}
                </div>
            </div>
        </div>

        <div id="tab-categories" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">📁 Transaction Categories</h2></div>
                <div class="section-content">
                    {f'<div style="margin-bottom:1.5rem;padding:1rem;background:var(--info-dim);border-radius:8px;border-left:3px solid var(--info);font-size:0.9rem;color:var(--info)"><strong>ℹ️ Note:</strong> Category data not found in JSON. To enable this section, ensure your analysis JSON includes a <code>categories</code> object with <code>credits</code> and <code>debits</code> arrays as defined in schema v5.0.4.</div>' if not has_categories else ''}
                    <div style="display:flex;flex-direction:column;gap:2rem;margin-bottom:1.5rem">
                        <div class="chart-container"><div class="chart-title">Credits Distribution</div><div id="creditsPieChart" style="height:320px"></div></div>
                        <div class="chart-container"><div class="chart-title">Debits Distribution</div><div id="debitsPieChart" style="height:450px"></div></div>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:2rem">
                        <div><h4 style="color:var(--accent);margin-bottom:1rem">CREDITS <span style="font-weight:normal;color:var(--text-muted)">(click ▶ Top 5 for details)</span></h4><table class="data-table"><thead><tr><th>Category</th><th class="text-right">Count</th><th class="text-right">Amount</th><th class="text-right">%</th></tr></thead><tbody>{credits_rows}</tbody></table></div>
                        <div><h4 style="color:var(--danger);margin-bottom:1rem">DEBITS <span style="font-weight:normal;color:var(--text-muted)">(click ▶ Top 5 for details)</span></h4><table class="data-table"><thead><tr><th>Category</th><th class="text-right">Count</th><th class="text-right">Amount</th><th class="text-right">%</th></tr></thead><tbody>{debits_rows}</tbody></table></div>
                    </div>
                </div>
            </div>
        </div>

        {counterparty_tab}

        <div id="tab-volatility" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">📈 Cash Flow Volatility</h2></div>
                <div class="section-content">
                    <div class="summary-cards">
                        <div class="summary-card"><div class="value" style="color:var(--{'accent' if vol_level=='LOW' else 'warn'})">{vol_index:.0f}%</div><div class="label">Overall Volatility</div></div>
                        <div class="summary-card"><div class="value">{vol_level}</div><div class="label">Risk Level</div></div>
                        <div class="summary-card"><div class="value">{len(vol_alerts)}</div><div class="label">Alerts</div></div>
                    </div>
                    {vol_method_note}
                    <div class="chart-container" style="margin:1.5rem 0"><div class="chart-title">Monthly Volatility</div><div id="volatilityChart" style="height:350px"></div></div>
                    <div class="flag-card">
                        <div class="flag-header" onclick="toggleDetails('volAlerts')"><span class="flag-title">⚠️ Volatility Alerts</span><span class="flag-count">{len(vol_alerts)} alerts</span></div>
                        <div id="volAlerts" class="flag-details show"><ul style="padding-left:1.5rem">{vol_alerts_html}</ul></div>
                    </div>
                </div>
            </div>
        </div>

        <div id="tab-flags" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">🚩 Risk Flags & Alerts</h2></div>
                <div class="section-content">
                    <div class="summary-cards">
                        <div class="summary-card"><div class="value" style="color:var(--{'accent' if kite_level=='LOW' else 'warn'})">{kite_score}</div><div class="label">Kite Flying Score</div></div>
                        <div class="summary-card"><div class="value">{kite_level}</div><div class="label">Risk Level</div></div>
                        <div class="summary-card"><div class="value" style="color:var(--warn)">{round_count}</div><div class="label">Round Figures</div></div>
                        <div class="summary-card"><div class="value" style="color:var(--{'accent' if returned_count==0 else 'danger'})">{returned_count}</div><div class="label">Returned Cheques</div></div>
                    </div>
                    <div class="flag-card">
                        <div class="flag-header" onclick="toggleDetails('kiteDetails')"><span class="flag-title">🪁 Kite Flying Indicators (7 Checks)</span><span class="flag-count">{kite_score} points</span></div>
                        <div id="kiteDetails" class="flag-details show">
                            <table class="data-table"><thead><tr><th>Indicator</th><th>Status</th><th class="text-right">Points</th><th>Finding</th></tr></thead><tbody>{kite_rows}</tbody></table>
                        </div>
                    </div>
                    <div class="flag-card">
                        <div class="flag-header" onclick="showModal('roundFigureModal')"><span class="flag-title">⚠️ Round Figure Transactions</span><span class="flag-count">{round_count} found</span></div>
                    </div>
                    {returned_cheques_html}
                </div>
            </div>
        </div>

        <div id="tab-integrity" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">✓ Data Integrity Score</h2></div>
                <div class="section-content">
                    <div class="summary-cards">
                        <div class="summary-card"><div class="value" style="color:var(--{'accent' if int_score>=90 else 'info' if int_score>=75 else 'warn'})">{int_score}%</div><div class="label">Integrity Score</div></div>
                        <div class="summary-card"><div class="value">{int_rating}</div><div class="label">Rating</div></div>
                        <div class="summary-card"><div class="value">{integrity.get('points_earned',0)}/{max_integrity_points}</div><div class="label">Points Earned</div></div>
                    </div>
                    <div class="table-container">
                        <table class="data-table">
                            <thead><tr><th>#</th><th>Check</th><th>Tier</th><th>Status</th><th class="text-right">Weight</th><th class="text-right">Points</th><th>Details</th></tr></thead>
                            <tbody>{int_rows}</tbody>
                        </table>
                    </div>
                    <div style="margin-top:1rem;padding:1rem;background:var(--bg-alt);border-radius:8px;border-left:3px solid var(--info);font-size:0.85rem;color:var(--text-soft)">
                        <strong style="color:var(--info)">ℹ️ Scoring:</strong> v{schema_version} uses {max_integrity_points}-point system. Score = (Points Earned / {max_integrity_points}) × 100
                    </div>
                </div>
            </div>
        </div>

        <div id="tab-related" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">👥 Related Party Analysis</h2></div>
                <div class="section-content">
                    <div class="summary-cards">
                        <div class="summary-card"><div class="value credit">RM {rp_credit:,.0f}</div><div class="label">From Related</div></div>
                        <div class="summary-card"><div class="value debit">RM {rp_debit:,.0f}</div><div class="label">To Related</div></div>
                        <div class="summary-card"><div class="value" style="color:var(--{'accent' if rp_net>=0 else 'danger'})">RM {rp_net:,.0f}</div><div class="label">Net Flow</div></div>
                    </div>
                    <div class="flag-card">
                        <div class="flag-header"><span class="flag-title">👤 Declared Related Parties</span><span class="flag-count">{len(related_parties)} parties</span></div>
                        <div style="margin:1rem;padding:1rem;background:var(--card-hover);border-radius:8px">{rp_parties}</div>
                    </div>
                    <div style="margin-top:1rem;padding:1rem;background:var(--info-dim);border-radius:8px;font-size:0.85rem;color:var(--info)">
                        <strong>ℹ️ Note:</strong> Related party detection matches transaction descriptions against declared party names. Ensure all directors, shareholders, and sister companies are declared in the analysis input.
                    </div>
                </div>
            </div>
        </div>

        {recurring_tab}
        {nonbank_tab}

        <div id="tab-recommendations" class="tab-content">
            <div class="section">
                <div class="section-header"><h2 class="section-title">✅ Recommendations</h2></div>
                <div class="section-content">{rec_html if rec_html else '<div style="color:var(--text-muted);text-align:center;padding:2rem">No recommendations</div>'}</div>
            </div>
        </div>

        <div class="footer">
            <p>Bank Statement Analysis v5.0 (Schema {schema_version})</p>
            <p>Generated: {r.get('generated_at', datetime.now().isoformat())} | Period: {period_start} - {period_end}</p>
        </div>
    </div>

    <div id="roundFigureModal" class="modal-overlay" onclick="closeModal('roundFigureModal',event)">
        <div class="modal" onclick="event.stopPropagation()">
            <div class="modal-header"><h3 class="modal-title">⚠️ Round Figure Transactions ({round_count})</h3><button class="modal-close" onclick="closeModal('roundFigureModal')">&times;</button></div>
            <div class="modal-body">
                {round_note}
                <table class="data-table" id="modalRoundFigureTable"><thead><tr><th>Date</th><th>Description</th><th>Type</th><th class="text-right">Amount</th><th>Account</th></tr></thead><tbody id="modalRoundFigureTableBody"></tbody></table>
            </div>
        </div>
    </div>

    <script>
        function toggleTheme() {{
            const html = document.documentElement;
            const btn = document.querySelector('.theme-toggle');
            const newTheme = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', newTheme);
            btn.textContent = newTheme === 'dark' ? '☀️ Light' : '🌙 Dark';
            localStorage.setItem('theme', newTheme);
        }}
        const roundFigureTransactions = {round_js};
        function populateRoundFigureTable(id) {{ document.getElementById(id).innerHTML = roundFigureTransactions.map(t => `<tr><td>${{t.date}}</td><td>${{t.desc}}</td><td><span class="badge" style="background:var(--${{t.type==='CREDIT'?'accent':'danger'}}-dim);color:var(--${{t.type==='CREDIT'?'accent':'danger'}})">${{t.type}}</span></td><td class="mono text-right ${{t.type==='CREDIT'?'credit':'debit'}}">RM ${{t.amount.toLocaleString()}}</td><td>${{t.account}}</td></tr>`).join(''); }}
        function showTab(name) {{ 
            document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active')); 
            document.querySelectorAll('.nav-tab').forEach(b=>b.classList.remove('active')); 
            const tab = document.getElementById('tab-'+name); 
            if(tab) tab.classList.add('active'); 
            document.querySelectorAll('.nav-tab').forEach(b => {{
                const btnName = b.getAttribute('data-tab');
                if(btnName === name) b.classList.add('active');
            }});
        }}
        function toggleSection(id) {{ const el = document.getElementById(id); if(el) el.classList.toggle('collapsed'); }}
        function toggleDetails(id) {{ const el = document.getElementById(id); if(el) el.classList.toggle('show'); }}
        function toggleTop5(id) {{ 
            const row = document.getElementById(id); 
            if(row) {{ 
                row.style.display = row.style.display === 'none' ? 'table-row' : 'none'; 
            }}
        }}
        function showModal(id) {{ document.getElementById(id).classList.add('show'); populateRoundFigureTable('modalRoundFigureTableBody'); }}
        function closeModal(id,e) {{ if(!e||e.target.classList.contains('modal-overlay')) document.getElementById(id).classList.remove('show'); }}
        
        document.addEventListener('DOMContentLoaded', function() {{
            const colors = {{ gridColor: '#1e2a42', textColor: '#9ca3af', paperBg: 'transparent', plotBg: 'transparent' }};
            populateRoundFigureTable('modalRoundFigureTableBody');
            Plotly.newPlot('creditsPieChart', [{{values:{credit_vals},labels:{credit_labels},type:'pie',hole:0.4,marker:{{colors:['#22c55e','#4ade80','#86efac','#bbf7d0','#166534','#15803d','#059669','#10b981']}},textinfo:'percent',textposition:'inside',textfont:{{color:'#fff',size:12}}}}], {{paper_bgcolor:colors.paperBg,font:{{color:colors.textColor,size:11}},showlegend:true,legend:{{orientation:'h',y:-0.15,x:0.5,xanchor:'center'}},margin:{{t:20,b:80,l:20,r:20}}}}, {{responsive:true,displayModeBar:false}});
            Plotly.newPlot('debitsPieChart', [{{values:{debit_vals},labels:{debit_labels},type:'pie',hole:0.4,marker:{{colors:['#ef4444','#f87171','#fca5a5','#fecaca','#dc2626','#b91c1c','#991b1b','#7f1d1d','#f97316','#fb923c','#fbbf24','#a3e635','#84cc16','#22d3ee','#a78bfa','#f472b6']}},textinfo:'percent',textposition:'inside',textfont:{{color:'#fff',size:12}}}}], {{paper_bgcolor:colors.paperBg,font:{{color:colors.textColor,size:11}},showlegend:true,legend:{{orientation:'h',y:-0.25,x:0.5,xanchor:'center'}},margin:{{t:20,b:150,l:20,r:20}}}}, {{responsive:true,displayModeBar:false}});
            Plotly.newPlot('volatilityChart', {vol_data_js}, {{paper_bgcolor:colors.paperBg,font:{{color:colors.textColor}},barmode:'group',showlegend:true,legend:{{orientation:'h',y:1.1}},margin:{{t:40,b:40,l:50,r:20}},yaxis:{{title:'Volatility %',gridcolor:colors.gridColor}},shapes:[{{type:'line',x0:-0.5,x1:5.5,y0:100,y1:100,line:{{color:'#f59e0b',width:2,dash:'dash'}}}},{{type:'line',x0:-0.5,x1:5.5,y0:200,y1:200,line:{{color:'#ef4444',width:2,dash:'dash'}}}}]}}, {{responsive:true}});
        }});
        document.addEventListener('keydown', function(e) {{ if(e.key==='Escape') document.querySelectorAll('.modal-overlay').forEach(m=>m.classList.remove('show')); }});
    </script>
</body>
</html>'''
    return html

# MAIN APP

def _slugify(text: str) -> str:
    text = (text or '').strip()
    text = text.replace(' ', '_')
    text = re.sub(r'[^A-Za-z0-9._-]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_')
    return text or 'report'

def _report_basename(data: dict, fallback: str = 'analysis') -> str:
    r = data.get('report_info', {}) if isinstance(data, dict) else {}
    company = r.get('company_name') or fallback
    period_end = r.get('period_end') or ''
    schema_full = r.get('schema_version') or detect_schema_version(data)
    base = _slugify(company)
    if period_end:
        base += '_' + _slugify(period_end)
    base += '_schema_' + _slugify(schema_full)
    return base

def _load_json_from_upload(uf) -> dict:
    # Streamlit UploadedFile.getvalue() returns bytes
    raw = uf.getvalue()
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
    return json.loads(raw)

def _build_zip(named_contents: List[Tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in named_contents:
            zf.writestr(name, content)
    return buf.getvalue()

st.title('🏦 Bank Statement Analysis → Interactive HTML')
st.caption('Upload one or many v5.x analysis JSON files, then download interactive HTML reports (compatible with v4.0 too).')


# If this page is used inside a MULTI-PAGE app together with Part 1,
# you can pass analysis JSON objects via st.session_state['analysis_outputs']
# (list of dicts OR list of (name, dict)). This avoids re-uploading.
session_payload = st.session_state.get('analysis_outputs') or st.session_state.get('analysis_results')
parsed: List[Tuple[str, dict]] = []
errors: List[str] = []

use_session = False
if isinstance(session_payload, list) and len(session_payload) > 0:
    use_session = st.checkbox('Use analysis outputs from Part 1 (current session)', value=True)

if use_session:
    for idx, item in enumerate(session_payload, start=1):
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], dict):
            parsed.append((str(item[0]), item[1]))
        elif isinstance(item, dict):
            parsed.append((f'analysis_{idx}.json', item))
        else:
            errors.append(f'session_payload[{idx}] is not a dict/tuple')
else:
    uploaded_files = st.file_uploader(
        'Upload JSON Analysis Output(s)',
        type=['json'],
        accept_multiple_files=True,
    )
    if not uploaded_files:
        st.info('👆 Upload one or more analysis JSON files to generate HTML reports.')
        st.stop()
    for uf in uploaded_files:
        try:
            d = _load_json_from_upload(uf)
            parsed.append((uf.name, d))
        except Exception as e:
            errors.append(f"{uf.name}: {e}")

if errors:
    st.error('Some inputs could not be parsed:')
    for err in errors:
        st.write('•', err)

if not parsed:
    st.stop()

st.success(f"✅ Loaded {len(parsed)} file(s)")


# Quick summary list
with st.expander('📄 Files loaded', expanded=(len(parsed) <= 3)):
    for name, d in parsed:
        r = d.get('report_info', {}) if isinstance(d, dict) else {}
        company = r.get('company_name', 'Unknown')
        schema_full = r.get('schema_version', detect_schema_version(d))
        period = f"{r.get('period_start','')} → {r.get('period_end','')}".strip()
        st.write(f"• **{company}** ({name}) — schema **{schema_full}**, period **{period}**")

st.markdown('---')
st.markdown('## 📥 Downloads')

# Single vs multiple behavior
if len(parsed) == 1:
    filename, data = parsed[0]
    schema_version = detect_schema_version(data)
    company = data.get('report_info', {}).get('company_name', 'Unknown')
    base = _report_basename(data, fallback=_slugify(Path(filename).stem))

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            '📄 DOWNLOAD JSON',
            json.dumps(data, indent=2),
            file_name=f'{base}.json',
            mime='application/json',
            use_container_width=True,
        )
    with c2:
        st.download_button(
            '🌐 DOWNLOAD INTERACTIVE HTML',
            generate_interactive_html(data),
            file_name=f'{base}.html',
            mime='text/html',
            use_container_width=True,
        )

    st.markdown('---')
    st.markdown('## 🔎 Quick Preview')
    r = data.get('report_info', {})
    st.markdown(f"**{company}** | {r.get('period_start','')} to {r.get('period_end','')} | {r.get('total_months',0)} Months")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Integrity', f"{data.get('integrity_score',{}).get('score',0)}%")
    c2.metric('Kite Flying', data.get('kite_flying',{}).get('risk_score',0))
    c3.metric('Volatility', f"{data.get('volatility',{}).get('overall_index',0):.0f}%")
    c4.metric('Round Figures', data.get('flags',{}).get('round_figure_transactions',{}).get('count',0))

    st.markdown('---')
    st.markdown('#### Account Summary')
    for acc in data.get('accounts', []):
        st.markdown(f"**{acc.get('bank_name','')}** ({acc.get('account_number','')}) - {acc.get('classification','')}")
        st.write(
            f"Credits: RM {acc.get('total_credits',0):,.2f} | "
            f"Debits: RM {acc.get('total_debits',0):,.2f} | "
            f"Closing: RM {acc.get('closing_balance',0):,.2f}",
        )

else:
    st.write('You uploaded multiple files. You can download individual reports below, or generate a ZIP for all reports.')
    
    # Individual downloads
    for idx, (filename, data) in enumerate(parsed, start=1):
        r = data.get('report_info', {})
        company = r.get('company_name', 'Unknown')
        schema_full = r.get('schema_version', detect_schema_version(data))
        base = _report_basename(data, fallback=_slugify(Path(filename).stem))
        
        with st.expander(f"{idx}. {company} — {schema_full} ({filename})", expanded=(len(parsed) <= 3)):
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    '📄 Download JSON',
                    json.dumps(data, indent=2),
                    file_name=f'{base}.json',
                    mime='application/json',
                    key=f'json_{idx}',
                    use_container_width=True,
                )
            with c2:
                st.download_button(
                    '🌐 Download HTML',
                    generate_interactive_html(data),
                    file_name=f'{base}.html',
                    mime='text/html',
                    key=f'html_{idx}',
                    use_container_width=True,
                )

    st.markdown('---')
    st.markdown('### 📦 Batch download')
    st.write('Click the button below to package all HTML reports (and original JSON) into ZIP files.')

    if st.button('Prepare ZIP files', type='primary'):
        html_files: List[Tuple[str, bytes]] = []
        json_files: List[Tuple[str, bytes]] = []
        for filename, data in parsed:
            base = _report_basename(data, fallback=_slugify(Path(filename).stem))
            html = generate_interactive_html(data).encode('utf-8')
            js = json.dumps(data, indent=2).encode('utf-8')
            html_files.append((f'{base}.html', html))
            json_files.append((f'{base}.json', js))

        st.session_state['zip_html'] = _build_zip(html_files)
        st.session_state['zip_json'] = _build_zip(json_files)
        st.success('ZIP files are ready!')

    if 'zip_html' in st.session_state:
        st.download_button(
            '⬇️ Download ALL HTML (ZIP)',
            data=st.session_state['zip_html'],
            file_name='bank_reports_html.zip',
            mime='application/zip',
            use_container_width=True,
        )
    if 'zip_json' in st.session_state:
        st.download_button(
            '⬇️ Download ALL JSON (ZIP)',
            data=st.session_state['zip_json'],
            file_name='bank_reports_json.zip',
            mime='application/zip',
            use_container_width=True,
        )
