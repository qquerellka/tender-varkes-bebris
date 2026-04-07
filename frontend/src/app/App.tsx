import { Suspense } from 'react'
import { ConfigProvider, theme } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import { RouterProvider } from 'react-router-dom'
import { AppLoader } from '@shared/ui/app-loader'
import { ReactQueryProvider } from './providers/app-providers'
import { router } from './router'

export function App() {
  return (
    <ReactQueryProvider>
      <ConfigProvider
        locale={ruRU}
        theme={{
          algorithm: theme.compactAlgorithm,
          token: {
            colorPrimary: '#cb3428',
            colorInfo: '#2f4f84',
            colorSuccess: '#1f7a4d',
            colorWarning: '#b76e16',
            colorError: '#b2343b',
            colorBgLayout: '#f2f4f6',
            colorBgContainer: '#ffffff',
            colorBorderSecondary: '#dde2e7',
            borderRadius: 4,
            fontFamily: '"Open Sans", "Segoe UI", Arial, sans-serif',
          },
        }}
      >
        <Suspense fallback={<AppLoader />}>
          <RouterProvider router={router} />
        </Suspense>
      </ConfigProvider>
    </ReactQueryProvider>
  )
}
