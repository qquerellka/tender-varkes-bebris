import type { PropsWithChildren } from 'react'

export default function Page({ children }: PropsWithChildren) {
  return (
    <main className="page">
      <div className="page__container">{children}</div>
    </main>
  )
}
