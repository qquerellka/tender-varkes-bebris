export default function AppLoader() {
  return (
    <div className="app-loader" role="status" aria-live="polite">
      <div className="app-loader__spinner" aria-hidden="true" />
      <span className="app-loader__label">Loading page...</span>
    </div>
  )
}
