<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import type { GlobalThemeOverrides } from 'naive-ui'

const FONT_SANS =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#3c96ca',
    primaryColorHover: '#2f86bd',
    primaryColorPressed: '#236b99',
    primaryColorSuppl: '#3c96ca',
    infoColor: '#3c96ca',
    infoColorHover: '#2f86bd',
    infoColorPressed: '#236b99',
    infoColorSuppl: '#3c96ca',
    successColor: '#1a7f37',
    successColorHover: '#188a3d',
    successColorPressed: '#157031',
    successColorSuppl: '#1a7f37',
    warningColor: '#9a6700',
    warningColorHover: '#aa7400',
    warningColorPressed: '#855c00',
    warningColorSuppl: '#9a6700',
    errorColor: '#cf222e',
    errorColorHover: '#d1242f',
    errorColorPressed: '#b3231b',
    errorColorSuppl: '#cf222e',
    bodyColor: '#eef2f6',
    textColorBase: '#1f2328',
    textColor1: '#1f2328',
    textColor2: '#656d76',
    textColor3: '#6e7781',
    placeholderColor: '#6e7781',
    dividerColor: '#e7eef5',
    borderColor: '#d6e0ea',
    borderRadius: '6px',
    borderRadiusSmall: '4px',
    fontFamily: FONT_SANS,
    fontSize: '14px',
    fontWeightStrong: '600',
  },
  DataTable: {
    thColor: '#eef2f6',
    thColorHover: '#e8f3fa',
    thTextColor: '#1f2328',
    thFontWeight: '600',
    tdColor: '#ffffff',
    tdColorHover: '#f6fbff',
    borderColor: '#d6e0ea',
  },
  Button: {
    color: '#eef2f6',
    colorHover: '#e8f3fa',
    colorPressed: '#dcecf6',
    colorFocus: '#e8f3fa',
    borderColor: 'rgba(31, 35, 40, 0.15)',
    borderColorHover: 'rgba(31, 35, 40, 0.15)',
    borderColorPressed: 'rgba(31, 35, 40, 0.15)',
    borderColorFocus: 'rgba(31, 35, 40, 0.15)',
    textColor: '#1f2328',
    textColorHover: '#1f2328',
    textColorPressed: '#1f2328',
    fontWeight: '500',
    borderRadiusMedium: '6px',
    borderRadiusSmall: '6px',
  },
  Tag: {
    color: '#eef2f6',
    textColor: '#1f2328',
    border: '1px solid transparent',
    colorPrimary: '#e8f3fa',
    textColorPrimary: '#2f86bd',
    borderPrimary: '1px solid transparent',
    colorInfo: '#e8f3fa',
    textColorInfo: '#2f86bd',
    borderInfo: '1px solid transparent',
    colorSuccess: '#dafbe1',
    textColorSuccess: '#1a7f37',
    borderSuccess: '1px solid transparent',
    colorWarning: '#fff8c5',
    textColorWarning: '#9a6700',
    borderWarning: '1px solid transparent',
    colorError: '#ffebe9',
    textColorError: '#cf222e',
    borderError: '1px solid transparent',
  },
  Menu: {
    itemColorHover: '#f6fbff',
    itemColorActive: '#e8f3fa',
    itemColorActiveHover: '#e8f3fa',
    itemTextColorActive: '#2f86bd',
    itemTextColorActiveHover: '#2f86bd',
    itemTextColorChildActive: '#2f86bd',
    itemTextColorChildActiveHover: '#2f86bd',
    itemIconColorActive: '#2f86bd',
    itemIconColorChildActive: '#2f86bd',
    borderRadius: '6px',
  },
  Input: {
    color: '#ffffff',
    colorFocus: '#ffffff',
    border: '1px solid #d6e0ea',
    borderHover: '1px solid #b9d5e8',
    borderFocus: '1px solid #3c96ca',
    boxShadowFocus: '0 0 0 3px rgba(60, 150, 202, 0.16)',
    borderRadius: '6px',
  },
  Layout: {
    color: '#eef2f6',
    headerColor: '#ffffff',
    siderColor: '#ffffff',
    siderBorderColor: '#d6e0ea',
    headerBorderColor: '#d6e0ea',
  },
  Card: {
    color: '#ffffff',
    colorModal: '#ffffff',
    borderColor: '#d6e0ea',
    borderRadius: '6px',
  },
  Tabs: {
    tabTextColorActiveLine: '#2f86bd',
    tabTextColorHoverLine: '#2f86bd',
    barColor: '#3c96ca',
  },
  Alert: {
    titleFontWeight: '600',
  },
}
</script>
