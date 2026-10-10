<#-- Тема subsidy: «Страница устарела» (форму отправили повторно, «Назад» или обновление) — объяснение и две кнопки вместо «Нажмите сюда» -->
<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        ${msg("pageExpiredTitle")}
    <#elseif section = "form">
        <div class="sc-result sc-result--warning">
            <span class="sc-result__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
            </span>
            <p id="instruction1" class="sc-result__text">${msg("scPageExpiredText")}</p>
            <div class="sc-result__actions">
                <a id="loginContinueLink" class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!}"
                   href="${url.loginAction}">${msg("scPageExpiredContinue")}</a>
                <a id="loginRestartLink" class="${properties.kcButtonClass!} ${properties.kcButtonSecondaryClass!} ${properties.kcButtonBlockClass!}"
                   href="${url.loginRestartFlowUrl}">${msg("scPageExpiredRestart")}</a>
            </div>
        </div>
    </#if>
</@layout.registrationLayout>
