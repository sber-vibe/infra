<#-- Тема subsidy: информационная страница (почта подтверждена, пароль изменён и т.п.) в том же виде, что и страница ошибки -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <#if messageHeader??>
            ${kcSanitize(msg("${messageHeader}"))?no_esc}
        <#else>
            ${message.summary}
        </#if>
    <#elseif section = "form">
        <div id="kc-info-message" class="sc-result sc-result--info">
            <span class="sc-result__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>
            </span>
            <p class="sc-result__text">${message.summary}<#if requiredActions??><#list requiredActions>: <b><#items as reqActionItem>${kcSanitize(msg("requiredAction.${reqActionItem}"))?no_esc}<#sep>, </#items></b></#list></#if></p>
            <#if !skipLink??>
                <#if pageRedirectUri?has_content>
                    <a class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!} sc-result__action" href="${pageRedirectUri}">${kcSanitize(msg("backToApplication"))?no_esc}</a>
                <#elseif actionUri?has_content>
                    <a class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!} sc-result__action" href="${actionUri}">${kcSanitize(msg("proceedWithAction"))?no_esc}</a>
                <#elseif (client.baseUrl)?has_content>
                    <a class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!} sc-result__action" href="${client.baseUrl}">${kcSanitize(msg("backToApplication"))?no_esc}</a>
                </#if>
            </#if>
        </div>
    </#if>
</@layout.registrationLayout>
