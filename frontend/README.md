# Insurance FAQ Chatbot - Frontend

A modern React-based frontend for the Insurance FAQ Chatbot system with full admin capabilities.

## Features

### User Features
- **Authentication**: Register and login with JWT-based authentication
- **Chat Interface**: Interactive chatbot with session-based conversation memory
- **Product Selection**: Filter questions by insurance product
- **Suggested Questions**: Pre-populated questions for quick access
- **Real-time Responses**: View answer sources, response time, and caching status

### Admin Features
- **Product Management**: Create, update, and delete insurance products
- **PDF Management**: Upload and manage PDF documents for knowledge base
- **FAQ Management**: Add pre-defined FAQs with multilingual support
- **User Management**: Manage user roles (admin/viewer)
- **Analytics Dashboard**: View chat statistics and audit logs
- **Cache Management**: Clear semantic cache, Redis cache, or entire knowledge base

## Tech Stack

- **React 18** - UI library
- **React Router** - Client-side routing
- **Axios** - HTTP client
- **Tailwind CSS** - Styling
- **Lucide React** - Icons
- **Vite** - Build tool

## Prerequisites

- Node.js 18+ and npm
- Backend API running on `http://localhost:8000`

## Installation

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Configuration (optional):

The API base URL is configured in `src/services/api.js`. Default is `http://localhost:8000/api`.

If your backend runs on a different port, update the `API_BASE_URL` constant:

```javascript
const API_BASE_URL = 'http://your-backend-url/api';
```

## Running the Application

### Development Mode

```bash
npm run dev
```

The application will start on `http://localhost:3000`

### Production Build

```bash
npm run build
```

The build output will be in the `dist` folder.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
frontend/
├── public/              # Static assets
├── src/
│   ├── components/      # Reusable components
│   │   ├── Layout.jsx
│   │   └── ProtectedRoute.jsx
│   ├── contexts/        # React contexts
│   │   └── AuthContext.jsx
│   ├── pages/           # Page components
│   │   ├── Login.jsx
│   │   ├── Register.jsx
│   │   ├── Chat.jsx
│   │   └── Admin.jsx
│   ├── services/        # API services
│   │   └── api.js
│   ├── App.jsx          # Main app component
│   ├── main.jsx         # Entry point
│   └── index.css        # Global styles
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## Usage

### For Regular Users

1. **Register**: Create an account (choose "Viewer" role)
2. **Login**: Use your credentials to log in
3. **Chat**: Ask questions about insurance policies
4. **Select Product**: Optionally filter by specific insurance products

### For Administrators

1. **Register**: Create an account with "Admin" role
2. **Access Admin Panel**: Click "Admin" in the navigation bar
3. **Manage Products**: Add/edit/delete insurance products
4. **Upload PDFs**: Upload policy documents for each product
5. **Manage FAQs**: Create pre-defined question-answer pairs
6. **View Analytics**: Monitor usage statistics and cache performance
7. **Manage Users**: Update user roles
8. **Cache Control**: Clear caches or reset knowledge base

## API Integration

The frontend integrates with the following API endpoints:

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login

### Chat
- `POST /api/chat/ask` - Submit questions
- `GET /api/chat/suggestions` - Get suggested questions

### Products
- `GET /api/products/` - List all products
- `POST /api/products/` - Create product (admin)
- `PUT /api/products/{id}` - Update product (admin)
- `DELETE /api/products/{id}` - Delete product (admin)

### Admin
- `POST /api/admin/upload-pdf` - Upload PDF
- `GET /api/admin/pdfs/{product_id}` - List PDFs
- `DELETE /api/admin/pdfs/{pdf_id}` - Delete PDF
- `POST /api/admin/products/{product_id}/pre-faq` - Add FAQ
- `GET /api/admin/products/{product_id}/pre-faq` - List FAQs
- `GET /api/admin/users` - List users
- `PUT /api/admin/users/{id}/role` - Update user role
- `GET /api/admin/audit` - Get audit logs
- `GET /api/admin/cache/stats` - Get cache statistics
- `DELETE /api/admin/cache/semantic` - Clear semantic cache
- `DELETE /api/admin/cache/redis` - Clear Redis cache
- `DELETE /api/admin/knowledge-base/clear` - Clear knowledge base

## Authentication

The app uses JWT tokens stored in localStorage. Tokens are automatically:
- Added to request headers via Axios interceptor
- Refreshed on app reload
- Cleared on logout or 401 responses

## Environment Variables

While the app doesn't require a `.env` file, you can configure:

- API URL in `src/services/api.js`
- Proxy settings in `vite.config.js`

## Troubleshooting

### CORS Errors
Ensure the backend has CORS enabled for `http://localhost:3000`

### API Connection Failed
1. Check backend is running on port 8000
2. Verify API_BASE_URL in `src/services/api.js`
3. Check browser console for specific errors

### Login Not Working
1. Verify backend database is running
2. Check network tab for response errors
3. Ensure user credentials are correct

## Development Notes

- Uses React Router v6 for navigation
- Authentication state managed via Context API
- All admin routes are protected by role checking
- Forms use controlled components pattern
- API calls use async/await with try/catch

## Contributing

When adding new features:
1. Add API endpoints to `src/services/api.js`
2. Create new pages in `src/pages/`
3. Add routes in `src/App.jsx`
4. Update this README with new features

## License

MIT License - See backend repository for details
