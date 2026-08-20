from html import escape

from app.application.notifications.message import MailMessage

# Taken from the web app so a mail looks like it came from the same product.
INK = "#1a2825"
BRAND = "#173f38"
BRAND_INK = "#f9f4e8"
PAGE = "#f4f1e9"
CARD = "#ffffff"
BORDER = "#e4ded1"
MUTED = "#66726d"
FAINT = "#8b938d"
PANEL = "#eef2ec"
RULE = "#efe9dc"
WARN_BG = "#f8e5df"
WARN_INK = "#94432f"

# Every client that matters falls back to Arial, and none of them fetch fonts.
FONT = "'Avenir Next','Segoe UI',Helvetica,Arial,sans-serif"


def _cell(content: str, padding: str = "0") -> str:
    return f'<tr><td style="padding:{padding};">{content}</td></tr>'


def _paragraph(text: str) -> str:
    return (
        f'<p style="margin:0 0 14px;color:{INK};font-size:15px;'
        f'line-height:1.65;">{escape(text)}</p>'
    )


def _figure(label: str, value: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        f' border="0"><tr><td style="background:{PANEL};border-radius:14px;'
        f'padding:18px 20px;">'
        f'<div style="color:{MUTED};font-size:11px;font-weight:700;'
        f'letter-spacing:0.06em;text-transform:uppercase;">{escape(label)}</div>'
        f'<div style="color:{BRAND};font-size:30px;font-weight:700;'
        f'padding-top:6px;letter-spacing:-0.02em;">{escape(value)}</div>'
        f"</td></tr></table>"
    )


def _rows(title: str | None, rows: tuple) -> str:
    heading = ""
    if title:
        heading = (
            f'<div style="color:{MUTED};font-size:11px;font-weight:700;'
            f'letter-spacing:0.06em;text-transform:uppercase;'
            f'padding-bottom:6px;">{escape(title)}</div>'
        )
    body = "".join(
        f'<tr><td style="padding:11px 0;border-bottom:1px solid {RULE};'
        f'color:{INK};font-size:14px;">{escape(row.label)}</td>'
        f'<td align="right" style="padding:11px 0;border-bottom:1px solid {RULE};'
        f'color:{INK};font-size:14px;font-weight:700;white-space:nowrap;">'
        f"{escape(row.value)}</td></tr>"
        for row in rows
    )
    return (
        f"{heading}"
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        f' border="0">{body}</table>'
    )


def _action(label: str, url: str) -> str:
    safe_url = escape(url, quote=True)
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td align="center" bgcolor="{BRAND}" style="border-radius:12px;">'
        f'<a href="{safe_url}" style="display:inline-block;padding:14px 28px;'
        f'color:{BRAND_INK};font-family:{FONT};font-size:15px;font-weight:700;'
        f'text-decoration:none;border-radius:12px;">{escape(label)}</a>'
        f"</td></tr></table>"
        # Some clients strip the button, and people forward these to a machine
        # where the link has to be copied by hand.
        f'<p style="margin:14px 0 0;color:{FAINT};font-size:12px;'
        f'line-height:1.6;word-break:break-all;">Bağlantı çalışmazsa bu adresi '
        f"tarayıcına yapıştır:<br>{escape(url)}</p>"
    )


def _notice(text: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        f' border="0"><tr><td style="background:{WARN_BG};border-radius:12px;'
        f'padding:14px 16px;color:{WARN_INK};font-size:13px;line-height:1.6;">'
        f"{escape(text)}</td></tr></table>"
    )


def render_html(message: MailMessage) -> str:
    blocks: list[str] = [
        _cell(
            f'<p style="margin:0 0 16px;color:{INK};font-size:17px;'
            f'font-weight:700;">{escape(message.greeting)}</p>'
        )
    ]
    if message.paragraphs:
        blocks.append(_cell("".join(_paragraph(p) for p in message.paragraphs)))
    if message.figure is not None:
        blocks.append(
            _cell(
                _figure(message.figure.label, message.figure.value),
                padding="6px 0 0",
            )
        )
    if message.rows:
        blocks.append(_cell(_rows(message.rows_title, message.rows), "22px 0 0"))
    if message.action is not None:
        blocks.append(
            _cell(_action(message.action.label, message.action.url), "24px 0 0")
        )
    if message.notice is not None:
        blocks.append(_cell(_notice(message.notice), "22px 0 0"))
    if message.footnote is not None:
        blocks.append(
            _cell(
                f'<p style="margin:0;color:{MUTED};font-size:13px;'
                f'line-height:1.6;">{escape(message.footnote)}</p>',
                "20px 0 0",
            )
        )

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
</head>
<body style="margin:0;padding:0;background:{PAGE};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
 style="background:{PAGE};font-family:{FONT};">
<tr><td align="center" style="padding:30px 12px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0"
 style="width:100%;max-width:600px;">
<tr><td style="padding:0 0 16px 2px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
<td width="40" height="40" align="center" valign="middle"
 style="width:40px;height:40px;background:{BRAND};border-radius:12px;
 color:{BRAND_INK};font-family:{FONT};font-size:18px;font-weight:700;">A</td>
<td style="padding-left:12px;color:{INK};font-size:16px;font-weight:700;">Accountant</td>
</tr></table>
</td></tr>
<tr><td style="background:{CARD};border:1px solid {BORDER};border-radius:18px;padding:30px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
{"".join(blocks)}
</table>
</td></tr>
<tr><td style="padding:16px 2px 0;color:{FAINT};font-size:12px;line-height:1.6;">
Bu mesaj Accountant hesabın için gönderildi. Bildirim tercihlerini uygulamanın
ayarlar bölümünden değiştirebilirsin.
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def render_text(message: MailMessage) -> str:
    """The plain-text half of the message.

    Sent alongside the markup rather than instead of it: text-only readers and
    spam filters both expect it, and a mail with no text part scores worse.
    """
    parts: list[str] = [message.greeting, ""]
    for paragraph in message.paragraphs:
        parts.extend([paragraph, ""])
    if message.figure is not None:
        parts.extend([f"{message.figure.label}: {message.figure.value}", ""])
    if message.rows:
        if message.rows_title:
            parts.append(f"{message.rows_title}:")
        parts.extend(f"- {row.label}: {row.value}" for row in message.rows)
        parts.append("")
    if message.action is not None:
        parts.extend([f"{message.action.label}:", message.action.url, ""])
    if message.notice is not None:
        parts.extend([message.notice, ""])
    if message.footnote is not None:
        parts.extend([message.footnote, ""])
    parts.append("Accountant")
    return "\n".join(parts)
