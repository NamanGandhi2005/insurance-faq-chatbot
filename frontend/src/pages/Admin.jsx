import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import {
  Package, Upload, FileText, Users, BarChart3,
  Trash2, Plus, Edit2, Settings, Database
} from 'lucide-react';
import { productsAPI, adminAPI } from '../services/api';

const Admin = () => {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('products');

  useEffect(() => {
    if (!isAdmin()) {
      navigate('/');
    }
  }, [isAdmin, navigate]);

  const tabs = [
    { id: 'products', label: 'Products', icon: Package },
    { id: 'pdfs', label: 'PDF Management', icon: Upload },
    { id: 'faqs', label: 'FAQs', icon: FileText },
    { id: 'users', label: 'Users', icon: Users },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'cache', label: 'Cache & System', icon: Database }
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center gap-3">
            <Settings className="w-8 h-8 text-indigo-600" />
            <h1 className="text-2xl font-bold text-gray-800">Admin Dashboard</h1>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="bg-white rounded-lg shadow-md mb-6">
          <div className="flex border-b overflow-x-auto">
            {tabs.map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors whitespace-nowrap ${
                    activeTab === tab.id
                      ? 'border-b-2 border-indigo-600 text-indigo-600'
                      : 'text-gray-600 hover:text-gray-800'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="p-6">
            {activeTab === 'products' && <ProductsTab />}
            {activeTab === 'pdfs' && <PDFsTab />}
            {activeTab === 'faqs' && <FAQsTab />}
            {activeTab === 'users' && <UsersTab />}
            {activeTab === 'analytics' && <AnalyticsTab />}
            {activeTab === 'cache' && <CacheTab />}
          </div>
        </div>
      </div>
    </div>
  );
};

const ProductsTab = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [formData, setFormData] = useState({ name: '', description: '' });

  useEffect(() => {
    loadProducts();
  }, []);

  const loadProducts = async () => {
    try {
      const response = await productsAPI.list();
      setProducts(response.data);
    } catch (error) {
      console.error('Failed to load products:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingProduct) {
        await productsAPI.update(editingProduct.id, formData);
      } else {
        await productsAPI.create(formData);
      }
      setShowForm(false);
      setEditingProduct(null);
      setFormData({ name: '', description: '' });
      loadProducts();
    } catch (error) {
      alert('Failed to save product: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleEdit = (product) => {
    setEditingProduct(product);
    setFormData({ name: product.name, description: product.description || '' });
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this product?')) return;
    try {
      await productsAPI.delete(id);
      loadProducts();
    } catch (error) {
      alert('Failed to delete product: ' + (error.response?.data?.detail || error.message));
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold">Product Management</h2>
        <button
          onClick={() => {
            setShowForm(!showForm);
            setEditingProduct(null);
            setFormData({ name: '', description: '' });
          }}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Product
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-50 p-4 rounded-lg mb-6">
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">Product Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              rows="3"
            />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
              {editingProduct ? 'Update' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setEditingProduct(null);
                setFormData({ name: '', description: '' });
              }}
              className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="space-y-4">
        {products.map(product => (
          <div key={product.id} className="border rounded-lg p-4 flex justify-between items-start">
            <div>
              <h3 className="font-semibold text-lg">{product.name}</h3>
              <p className="text-gray-600 text-sm">{product.description}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleEdit(product)}
                className="p-2 text-blue-600 hover:bg-blue-50 rounded"
              >
                <Edit2 className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleDelete(product.id)}
                className="p-2 text-red-600 hover:bg-red-50 rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const PDFsTab = () => {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [pdfs, setPdfs] = useState([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadProducts();
  }, []);

  useEffect(() => {
    if (selectedProduct) {
      loadPDFs();
    }
  }, [selectedProduct]);

  const loadProducts = async () => {
    try {
      const response = await productsAPI.list();
      setProducts(response.data);
      if (response.data.length > 0) {
        setSelectedProduct(response.data[0].id);
      }
    } catch (error) {
      console.error('Failed to load products:', error);
    }
  };

  const loadPDFs = async () => {
    if (!selectedProduct) return;
    try {
      const response = await adminAPI.listPDFs(selectedProduct);
      setPdfs(response.data);
    } catch (error) {
      console.error('Failed to load PDFs:', error);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    try {
      await adminAPI.uploadPDF(selectedProduct, file);
      loadPDFs();
      e.target.value = '';
    } catch (error) {
      alert('Failed to upload PDF: ' + (error.response?.data?.detail || error.message));
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (pdfId) => {
    if (!confirm('Are you sure you want to delete this PDF?')) return;
    try {
      await adminAPI.deletePDF(pdfId);
      loadPDFs();
    } catch (error) {
      alert('Failed to delete PDF');
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">PDF Management</h2>

      <div className="mb-6">
        <label className="block text-sm font-medium mb-2">Select Product</label>
        <select
          value={selectedProduct}
          onChange={(e) => setSelectedProduct(e.target.value)}
          className="w-full max-w-md px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {products.map(product => (
            <option key={product.id} value={product.id}>{product.name}</option>
          ))}
        </select>
      </div>

      <div className="mb-6">
        <label className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 cursor-pointer inline-flex items-center gap-2">
          <Upload className="w-4 h-4" />
          {uploading ? 'Uploading...' : 'Upload PDF'}
          <input
            type="file"
            accept=".pdf"
            onChange={handleUpload}
            className="hidden"
            disabled={uploading || !selectedProduct}
          />
        </label>
      </div>

      <div className="space-y-3">
        {pdfs.map(pdf => (
          <div key={pdf.id} className="border rounded-lg p-4 flex justify-between items-center">
            <div>
              <p className="font-medium">{pdf.file_name}</p>
              <div className="flex gap-4 text-sm text-gray-600 mt-1">
                <span>Status: <span className={`font-medium ${
                  pdf.status === 'completed' ? 'text-green-600' :
                  pdf.status === 'processing' ? 'text-yellow-600' :
                  pdf.status === 'error' ? 'text-red-600' : 'text-gray-600'
                }`}>{pdf.status}</span></span>
                <span>Chunks: {pdf.chunk_count}</span>
                <span>Size: {(pdf.file_size / 1024).toFixed(2)} KB</span>
              </div>
            </div>
            <button
              onClick={() => handleDelete(pdf.id)}
              className="p-2 text-red-600 hover:bg-red-50 rounded"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

const FAQsTab = () => {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [faqs, setFaqs] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingFaq, setEditingFaq] = useState(null);
  const [formData, setFormData] = useState({ question: '', answer: '', language: 'en' });

  useEffect(() => {
    loadProducts();
  }, []);

  useEffect(() => {
    if (selectedProduct) {
      loadFAQs();
    }
  }, [selectedProduct]);

  const loadProducts = async () => {
    try {
      const response = await productsAPI.list();
      setProducts(response.data);
      if (response.data.length > 0) {
        setSelectedProduct(response.data[0].id);
      }
    } catch (error) {
      console.error('Failed to load products:', error);
    }
  };

  const loadFAQs = async () => {
    if (!selectedProduct) return;
    try {
      const response = await adminAPI.getFAQs(selectedProduct);
      setFaqs(response.data);
    } catch (error) {
      console.error('Failed to load FAQs:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingFaq) {
        await adminAPI.updateFAQ(selectedProduct, editingFaq.id, formData);
      } else {
        await adminAPI.addFAQ(selectedProduct, formData);
      }
      setShowForm(false);
      setEditingFaq(null);
      setFormData({ question: '', answer: '', language: 'en' });
      loadFAQs();
    } catch (error) {
      alert('Failed to save FAQ');
    }
  };

  const handleDelete = async (faqId) => {
    if (!confirm('Are you sure you want to delete this FAQ?')) return;
    try {
      await adminAPI.deleteFAQ(selectedProduct, faqId);
      loadFAQs();
    } catch (error) {
      alert('Failed to delete FAQ');
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">FAQ Management</h2>

      <div className="mb-6">
        <label className="block text-sm font-medium mb-2">Select Product</label>
        <select
          value={selectedProduct}
          onChange={(e) => setSelectedProduct(e.target.value)}
          className="w-full max-w-md px-4 py-2 border rounded-lg"
        >
          {products.map(product => (
            <option key={product.id} value={product.id}>{product.name}</option>
          ))}
        </select>
      </div>

      <button
        onClick={() => setShowForm(!showForm)}
        className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 mb-6 flex items-center gap-2"
      >
        <Plus className="w-4 h-4" />
        Add FAQ
      </button>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-50 p-4 rounded-lg mb-6">
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">Question</label>
            <input
              type="text"
              value={formData.question}
              onChange={(e) => setFormData({ ...formData, question: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">Answer</label>
            <textarea
              value={formData.answer}
              onChange={(e) => setFormData({ ...formData, answer: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg"
              rows="4"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">Language</label>
            <select
              value={formData.language}
              onChange={(e) => setFormData({ ...formData, language: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg"
            >
              <option value="en">English</option>
              <option value="hi">Hindi</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-lg">
              {editingFaq ? 'Update' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setEditingFaq(null);
                setFormData({ question: '', answer: '', language: 'en' });
              }}
              className="px-4 py-2 bg-gray-300 rounded-lg"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="space-y-4">
        {faqs.map(faq => (
          <div key={faq.id} className="border rounded-lg p-4">
            <div className="flex justify-between items-start mb-2">
              <h3 className="font-semibold">{faq.question}</h3>
              <button
                onClick={() => handleDelete(faq.id)}
                className="p-2 text-red-600 hover:bg-red-50 rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
            <p className="text-gray-600 text-sm">{faq.answer}</p>
            <span className="inline-block mt-2 text-xs bg-gray-200 px-2 py-1 rounded">
              {faq.language}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

const UsersTab = () => {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const response = await adminAPI.listUsers();
      setUsers(response.data);
    } catch (error) {
      console.error('Failed to load users:', error);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    try {
      await adminAPI.updateUserRole(userId, newRole);
      loadUsers();
    } catch (error) {
      alert('Failed to update user role: ' + (error.response?.data?.detail || error.message));
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">User Management</h2>

      <div className="space-y-3">
        {users.map(user => (
          <div key={user.id} className="border rounded-lg p-4 flex justify-between items-center">
            <div>
              <p className="font-medium">{user.full_name || user.email}</p>
              <p className="text-sm text-gray-600">{user.email}</p>
              <p className="text-xs text-gray-500 mt-1">
                Created: {new Date(user.created_at).toLocaleDateString()}
              </p>
            </div>
            <div>
              <select
                value={user.role}
                onChange={(e) => handleRoleChange(user.id, e.target.value)}
                className="px-3 py-1 border rounded-lg text-sm"
              >
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const AnalyticsTab = () => {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    loadStats();
    loadLogs();
  }, []);

  const loadStats = async () => {
    try {
      const response = await adminAPI.getCacheStats();
      setStats(response.data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const loadLogs = async () => {
    try {
      const response = await adminAPI.getAuditLogs(50);
      setLogs(response.data);
    } catch (error) {
      console.error('Failed to load logs:', error);
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Analytics & Audit Logs</h2>

      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-blue-600 font-medium">Total Requests</p>
            <p className="text-3xl font-bold text-blue-900">{stats.total_requests}</p>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-sm text-green-600 font-medium">Cache Hits</p>
            <p className="text-3xl font-bold text-green-900">{stats.cache_hits}</p>
          </div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-sm text-yellow-600 font-medium">Hit Rate</p>
            <p className="text-3xl font-bold text-yellow-900">{stats.hit_rate_percentage}%</p>
          </div>
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <p className="text-sm text-purple-600 font-medium">Avg Response</p>
            <p className="text-3xl font-bold text-purple-900">{stats.average_response_time_sec}s</p>
          </div>
        </div>
      )}

      <h3 className="text-lg font-semibold mb-4">Recent Queries</h3>
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {logs.map(log => (
          <div key={log.id} className="border rounded-lg p-4">
            <p className="font-medium text-sm">{log.question}</p>
            <p className="text-xs text-gray-600 mt-2 line-clamp-2">{log.answer}</p>
            <div className="flex gap-4 mt-2 text-xs text-gray-500">
              <span>{new Date(log.created_at).toLocaleString()}</span>
              <span>{log.response_time_ms.toFixed(2)}ms</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const CacheTab = () => {
  const handleClearCache = async (type) => {
    const messages = {
      semantic: 'This will clear all semantic cached Q&A pairs.',
      redis: 'This will clear Redis cache.',
      knowledge: 'WARNING: This will delete ALL document embeddings!'
    };

    if (!confirm(messages[type] + ' Continue?')) return;

    try {
      if (type === 'semantic') await adminAPI.clearSemanticCache();
      if (type === 'redis') await adminAPI.clearRedisCache();
      if (type === 'knowledge') await adminAPI.clearKnowledgeBase();
      alert('Cache cleared successfully!');
    } catch (error) {
      alert('Failed to clear cache: ' + (error.response?.data?.detail || error.message));
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Cache & System Management</h2>

      <div className="space-y-4">
        <div className="border rounded-lg p-4">
          <h3 className="font-semibold mb-2">Semantic Cache (ChromaDB)</h3>
          <p className="text-sm text-gray-600 mb-4">
            Clear cached question-answer pairs from vector database.
          </p>
          <button
            onClick={() => handleClearCache('semantic')}
            className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700"
          >
            Clear Semantic Cache
          </button>
        </div>

        <div className="border rounded-lg p-4">
          <h3 className="font-semibold mb-2">Redis Cache</h3>
          <p className="text-sm text-gray-600 mb-4">
            Clear Redis cache including rate limits and temporary data.
          </p>
          <button
            onClick={() => handleClearCache('redis')}
            className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
          >
            Clear Redis Cache
          </button>
        </div>

        <div className="border border-red-300 rounded-lg p-4 bg-red-50">
          <h3 className="font-semibold mb-2 text-red-800">Knowledge Base</h3>
          <p className="text-sm text-red-700 mb-4">
            WARNING: This will delete ALL document embeddings. The chatbot will forget all PDF content.
          </p>
          <button
            onClick={() => handleClearCache('knowledge')}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
          >
            Clear Knowledge Base
          </button>
        </div>
      </div>
    </div>
  );
};

export default Admin;
