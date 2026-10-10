<#-- Обёртка писем «СубсидияЧек»: таблицы и инлайн-стили — так письмо одинаково выглядит в Яндекс Почте, Gmail и Outlook -->
<#macro emailLayout>
<!DOCTYPE html>
<html lang="${locale.language}" dir="${(ltr)?then('ltr','rtl')}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>${realmName}</title>
</head>
<body style="margin:0;padding:0;background:#f2f4f7;font-family:Manrope,'Segoe UI',Roboto,Arial,sans-serif;color:#1f1f22;-webkit-font-smoothing:antialiased;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f2f4f7;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;">
          <tr>
            <td style="background:#21a038;background-image:linear-gradient(120deg,#107f2c 0%,#21a038 45%,#1fb57d 75%,#0a9cc4 100%);border-radius:24px 24px 0 0;padding:28px 32px;">
              <span style="display:inline-block;width:30px;height:30px;line-height:30px;border-radius:50%;background:#ffffff;color:#21a038;font-size:18px;font-weight:800;text-align:center;vertical-align:middle;">&#10003;</span>
              <span style="margin-left:10px;color:#ffffff;font-size:20px;font-weight:700;vertical-align:middle;">Субсидия<b style="font-weight:800;">Чек</b></span>
            </td>
          </tr>
          <tr>
            <td style="background:#ffffff;border-radius:0 0 24px 24px;padding:32px;font-size:15px;line-height:1.6;box-shadow:0 12px 32px rgba(16,24,40,0.06);">
              <#nested>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px 0;color:#8a9099;font-size:12px;line-height:1.5;text-align:center;">
              ${msg("scEmailFooter", realmName)}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
</#macro>

<#-- Крупная кнопка-ссылка и запасная ссылка текстом -->
<#macro button link label>
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0;">
    <tr>
      <td style="border-radius:14px;background:#21a038;">
        <a href="${link}" target="_blank" style="display:inline-block;padding:14px 28px;color:#ffffff;font-size:16px;font-weight:700;text-decoration:none;border-radius:14px;">${label}</a>
      </td>
    </tr>
  </table>
  <p style="margin:0 0 6px;color:#8a9099;font-size:13px;">${msg("scEmailLinkFallback")}</p>
  <p style="margin:0 0 20px;font-size:13px;word-break:break-all;"><a href="${link}" style="color:#1a8c30;">${link}</a></p>
</#macro>
