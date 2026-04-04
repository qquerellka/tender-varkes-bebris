import { Link } from 'react-router-dom'
import { Page } from '@shared/ui/page'

export function NotFoundPage() {
  return (
    <Page>
      <section className="not-found-page">
        <p className="not-found-page__eyebrow">404</p>
        <h1 className="not-found-page__title">Page not found</h1>
        <p className="not-found-page__description">
          Такой страницы нет в текущем роутинге. Вернитесь на главную и
          продолжайте собирать приложение по слоям.
        </p>
        <Link className="not-found-page__link" to="/">
          На главную
        </Link>
      </section>
    </Page>
  )
}

export default NotFoundPage;