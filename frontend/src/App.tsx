
import { BrowserRouter } from 'react-router-dom';
import { AppRouter } from './routes/AppRouter';
import './index.css'; // Design tokens and base styles
import { AuthProvider } from './contexts/AuthContext';
import { BranchProvider } from './contexts/BranchContext';
import { ThemeProvider } from './contexts/ThemeContext';

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <BranchProvider>
            <AppRouter />
          </BranchProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
