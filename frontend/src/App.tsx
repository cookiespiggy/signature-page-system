import { BrowserRouter, Route, Routes } from "react-router-dom"

import { ErrorBoundary } from "@/components/ErrorBoundary"
import { AppLayout } from "@/components/layout/AppLayout"
import { DetailPage } from "@/pages/DetailPage"
import { ListPage } from "@/pages/ListPage"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route
            index
            element={
              <ErrorBoundary>
                <ListPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="projects/:id"
            element={
              <ErrorBoundary>
                <DetailPage />
              </ErrorBoundary>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
