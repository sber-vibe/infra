<#-- Тема subsidy: «Подтвердите почту» — значок письма, адрес и кнопка повторной отправки вместо «Нажмите сюда» -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        ${msg("emailVerifyTitle")}
    <#elseif section = "form">
        <div class="sc-result sc-result--info">
            <span class="sc-result__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>
            </span>
            <p class="sc-result__text">
                <#if verifyEmail??>
                    ${kcSanitize(msg("scVerifySent", verifyEmail))?no_esc}
                <#else>
                    ${kcSanitize(msg("scVerifySent", user.email))?no_esc}
                </#if>
            </p>
            <#if isAppInitiatedAction??>
                <form id="kc-verify-email-form" class="sc-result__actions" action="${url.loginAction}" method="post">
                    <button class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!}" type="submit">${msg("scVerifyResend")}</button>
                    <button class="${properties.kcButtonClass!} ${properties.kcButtonSecondaryClass!} ${properties.kcButtonBlockClass!}" type="submit" name="cancel-aia" value="true" formnovalidate>${msg("doCancel")}</button>
                </form>
            <#else>
                <p class="sc-result__hint">${msg("scVerifyNoEmail")}</p>
                <div class="sc-result__actions">
                    <a class="${properties.kcButtonClass!} ${properties.kcButtonSecondaryClass!} ${properties.kcButtonBlockClass!}" href="${url.loginAction}">${msg("scVerifyResend")}</a>
                </div>
            </#if>
        </div>
    </#if>
</@layout.registrationLayout>
