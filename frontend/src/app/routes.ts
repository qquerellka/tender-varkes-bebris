import { createElement, lazy } from 'react'
import type { RouteObject } from 'react-router-dom'

const HomePageLazy = lazy(() => import('@pages/HomePage'))
const ProductPageLazy = lazy(() => import('@pages/ProductPage'))
const CartPageLazy = lazy(() => import('@pages/CartPage'))
const SupplierPageLazy = lazy(() => import('@pages/SupplierPage'))
const TelemetryDebugPageLazy = lazy(() => import('@pages/TelemetryDebugPage'))
const NotFoundPageLazy = lazy(() => import('@pages/not-found'))

export const routes: RouteObject[] = [
  {
    path: '/',
    element: createElement(HomePageLazy),
  },
  {
    path: '/product/:steId',
    element: createElement(ProductPageLazy),
  },
  {
    path: '/cart',
    element: createElement(CartPageLazy),
  },
  {
    path: '/supplier',
    element: createElement(SupplierPageLazy),
  },
  {
    path: '/debug/telemetry',
    element: createElement(TelemetryDebugPageLazy),
  },
  {
    path: '*',
    element: createElement(NotFoundPageLazy),
  },
]
