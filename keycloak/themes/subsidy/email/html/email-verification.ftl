<#import "template.ftl" as layout>
<@layout.emailLayout>
<h1 style="margin:0 0 12px;font-size:24px;font-weight:800;letter-spacing:-0.01em;">${msg("scVerifyTitle")}</h1>
<p style="margin:0;">${msg("scVerifyText", realmName)}</p>
<@layout.button link=link label=msg("scVerifyButton")/>
<p style="margin:0 0 8px;color:#565b62;">${msg("scLinkExpires", linkExpirationFormatter(linkExpiration))}</p>
<p style="margin:0;color:#565b62;">${msg("scVerifyIgnore")}</p>
</@layout.emailLayout>
