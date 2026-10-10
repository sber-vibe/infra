<#-- Тема subsidy: страница ошибки (не ушло письмо, вход устарел и т.п.) — значок, понятный текст и кнопка вместо голой ссылки -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        ${kcSanitize(msg("errorTitle"))?no_esc}
    <#elseif section = "form">
        <div id="kc-error-message" class="sc-result sc-result--error">
            <span class="sc-result__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="M12 8v5m0 3.5v.01M10.3 3.9 2.6 17.3A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.7L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
            </span>
            <p class="sc-result__text">${kcSanitize(message.summary)?no_esc}</p>
            <#if !skipLink?? && client?? && client.baseUrl?has_content>
                <a id="backToApplication" class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!} sc-result__action"
                   href="${client.baseUrl}">${kcSanitize(msg("backToApplication"))?no_esc}</a>
            </#if>
        </div>
    </#if>
</@layout.registrationLayout>
