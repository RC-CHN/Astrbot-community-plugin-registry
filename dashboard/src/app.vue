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
    primaryColor: '#0969da',
    primaryColorHover: '#0860ca',
    primaryColorPressed: '#0550ae',
    primaryColorSuppl: '#0969da',
    infoColor: '#0969da',
    infoColorHover: '#0860ca',
    infoColorPressed: '#0550ae',
    infoColorSuppl: '#0969da',
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
    bodyColor: '#f6f8fa',
    textColorBase: '#1f2328',
    textColor1: '#1f2328',
    textColor2: '#656d76',
    textColor3: '#6e7781',
    placeholderColor: '#6e7781',
    dividerColor: '#eaeef2',
    borderColor: '#d0d7de',
    borderRadius: '6px',
    borderRadiusSmall: '4px',
    fontFamily: FONT_SANS,
    fontSize: '14px',
    fontWeightStrong: '600',
  },
  DataTable: {
    thColor: '#f6f8fa',
    thColorHover: '#f3f4f6',
    thTextColor: '#1f2328',
    thFontWeight: '600',
    tdColor: '#ffffff',
    tdColorHover: '#f6f8fa',
    borderColor: '#d0d7de',
  },
  Button: {
    color: '#f6f8fa',
    colorHover: '#f3f4f6',
    colorPressed: '#eaeef2',
    colorFocus: '#f3f4f6',
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
    color: '#eaeef2',
    textColor: '#1f2328',
    border: '1px solid transparent',
    colorPrimary: '#ddf4ff',
    textColorPrimary: '#0969da',
    borderPrimary: '1px solid transparent',
    colorInfo: '#ddf4ff',
    textColorInfo: '#0969da',
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
    itemColorHover: '#f6f8fa',
    itemColorActive: '#ddf4ff',
    itemColorActiveHover: '#ddf4ff',
    itemTextColorActive: '#0969da',
    itemTextColorActiveHover: '#0969da',
    itemTextColorChildActive: '#0969da',
    itemTextColorChildActiveHover: '#0969da',
    itemIconColorActive: '#0969da',
    itemIconColorChildActive: '#0969da',
    borderRadius: '6px',
  },
  Input: {
    color: '#ffffff',
    colorFocus: '#ffffff',
    border: '1px solid #d0d7de',
    borderHover: '1px solid #d0d7de',
    borderFocus: '1px solid #0969da',
    boxShadowFocus: '0 0 0 3px rgba(9, 105, 218, 0.15)',
    borderRadius: '6px',
  },
  Layout: {
    color: '#f6f8fa',
    headerColor: '#ffffff',
    siderColor: '#ffffff',
    siderBorderColor: '#d0d7de',
    headerBorderColor: '#d0d7de',
  },
  Card: {
    color: '#ffffff',
    colorModal: '#ffffff',
    borderColor: '#d0d7de',
    borderRadius: '6px',
  },
  Tabs: {
    tabTextColorActiveLine: '#0969da',
    tabTextColorHoverLine: '#0969da',
    barColor: '#0969da',
  },
  Alert: {
    titleFontWeight: '600',
  },
}
</script>
