import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import {
  Package, Upload, FileText, Users, BarChart3,
  Trash2, Plus, Edit2, Settings, Database
} from 'lucide-react';
import { productsAPI, adminAPI } from '../services/api';

const SkeletonLoader = () => (
  <div className="space-y-4">
    {[...Array(3)].map((_, i) => (
      <div key={i} className="border dark:border-gray-700 rounded-lg p-4 animate-pulse">
        <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3 mt-2"></div>
      </div>
    ))}
  </div>
);

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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center gap-3">
            <Settings className="w-8 h-8 text-indigo-600 dark:text-indigo-400" />
            <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-200">Admin Dashboard</h1>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md mb-6">
          <div className="flex border-b dark:border-gray-700 overflow-x-auto">
            {tabs.map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors whitespace-nowrap ${
                    activeTab === tab.id
                      ? 'border-b-2 border-indigo-600 text-indigo-600 dark:text-indigo-400'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
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
    setLoading(true);
    try {
      const response = await productsAPI.list();
      setProducts(response.data);
    } catch (error) {
      toast.error('Failed to load products.');
      console.error('Failed to load products:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const promise = editingProduct 
      ? productsAPI.update(editingProduct.id, formData)
      : productsAPI.create(formData);

    toast.promise(promise, {
      loading: 'Saving product...',
      success: () => {
        setShowForm(false);
        setEditingProduct(null);
        setFormData({ name: '', description: '' });
        loadProducts();
        return editingProduct ? 'Product updated successfully!' : 'Product created successfully!';
      },
      error: (error) => `Failed to save product: ${error.response?.data?.detail || error.message}`
    });
  };

  const handleEdit = (product) => {
    setEditingProduct(product);
    setFormData({ name: product.name, description: product.description || '' });
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this product? This will also delete associated PDFs and FAQs.')) return;
    
    toast.promise(productsAPI.delete(id), {
      loading: 'Deleting product...',
      success: () => {
        loadProducts();
        return 'Product deleted successfully!';
      },
      error: (error) => `Failed to delete product: ${error.response?.data?.detail || error.message}`
    });
  };

  if (loading) return <SkeletonLoader />;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold dark:text-gray-200">Product Management</h2>
        <button
          onClick={() => {
            setShowForm(!showForm);
            setEditingProduct(null);
            setFormData({ name: '', description: '' });
          }}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          {showForm ? 'Cancel' : 'Add Product'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg mb-6">
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2 dark:text-gray-300">Product Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white dark:bg-gray-800 dark:border-gray-600"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2 dark:text-gray-300">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white dark:bg-gray-800 dark:border-gray-600"
              rows="3"
            />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
              {editingProduct ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      )}

      <div className="space-y-4">
        {products.map(product => (
          <div key={product.id} className="border dark:border-gray-700 rounded-lg p-4 flex justify-between items-start">
            <div>
              <h3 className="font-semibold text-lg dark:text-gray-200">{product.name}</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">{product.description}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleEdit(product)}
                className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-gray-700 rounded"
              >
                <Edit2 className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleDelete(product.id)}
                className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-gray-700 rounded"
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
  const [loading, setLoading] = useState(true);
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
    setLoading(true);
    try {
      const response = await productsAPI.list();
      setProducts(response.data);
      if (response.data.length > 0) {
        setSelectedProduct(response.data[0].id);
      }
    } catch (error) {
      toast.error('Failed to load products.');
      console.error('Failed to load products:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadPDFs = async () => {
    if (!selectedProduct) return;
    setLoading(true);
    try {
      const response = await adminAPI.listPDFs(selectedProduct);
      setPdfs(response.data);
    } catch (error) {
      toast.error('Failed to load PDFs.');
      console.error('Failed to load PDFs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    const promise = adminAPI.uploadPDF(selectedProduct, file);

    toast.promise(promise, {
      loading: 'Uploading PDF...',
      success: () => {
        e.target.value = '';
        loadPDFs();
        return 'PDF uploaded successfully!';
      },
      error: (error) => `Failed to upload PDF: ${error.response?.data?.detail || error.message}`
    });

    try {
      await promise;
    } catch (error) {
      // prevent unhandled promise rejection
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (pdfId) => {
    if (!confirm('Are you sure you want to delete this PDF?')) return;
    
    toast.promise(adminAPI.deletePDF(pdfId), {
      loading: 'Deleting PDF...',
      success: () => {
        loadPDFs();
        return 'PDF deleted successfully!';
      },
      error: 'Failed to delete PDF'
    });
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6 dark:text-gray-200">PDF Management</h2>

      <div className="mb-6">
        <label className="block text-sm font-medium mb-2 dark:text-gray-300">Select Product</label>
        <select
          value={selectedProduct}
          onChange={(e) => setSelectedProduct(e.target.value)}
          className="w-full max-w-md px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white dark:bg-gray-800 dark:border-gray-600"
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
      
      {loading ? <SkeletonLoader /> : (
        <div className="space-y-3">
          {pdfs.map(pdf => (
            <div key={pdf.id} className="border dark:border-gray-700 rounded-lg p-4 flex justify-between items-center">
              <div>
                <p className="font-medium dark:text-gray-200">{pdf.file_name}</p>
                <div className="flex gap-4 text-sm text-gray-600 dark:text-gray-400 mt-1">
                  <span>Status: <span className={`font-medium ${
                    pdf.status === 'completed' ? 'text-green-600 dark:text-green-400' :
                    pdf.status === 'processing' ? 'text-yellow-600 dark:text-yellow-400' :
                    pdf.status === 'error' ? 'text-red-600 dark:text-red-400' : 'text-gray-600 dark:text-gray-400'
                  }`}>{pdf.status}</span></span>
                  <span>Chunks: {pdf.chunk_count}</span>
                  <span>Size: {(pdf.file_size / 1024).toFixed(2)} KB</span>
                </div>
              </div>
              <button
                onClick={() => handleDelete(pdf.id)}
                className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-gray-700 rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const FAQsTab = () => {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [faqs, setFaqs] = useState([]);
  const [loading, setLoading] = useState(true);
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
    setLoading(true);
    try {
      const response = await productsAPI.list();
      setProducts(response.data);
      if (response.data.length > 0) {
        setSelectedProduct(response.data[0].id);
      }
    } catch (error) {
      toast.error('Failed to load products.');
      console.error('Failed to load products:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadFAQs = async () => {
    if (!selectedProduct) return;
    setLoading(true);
    try {
      const response = await adminAPI.getFAQs(selectedProduct);
      setFaqs(response.data);
    } catch (error) {
      toast.error('Failed to load FAQs.');
      console.error('Failed to load FAQs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const promise = editingFaq
      ? adminAPI.updateFAQ(selectedProduct, editingFaq.id, formData)
      : adminAPI.addFAQ(selectedProduct, formData);

    toast.promise(promise, {
      loading: 'Saving FAQ...',
      success: () => {
        setShowForm(false);
        setEditingFaq(null);
        setFormData({ question: '', answer: '', language: 'en' });
        loadFAQs();
        return 'FAQ saved successfully!';
      },
      error: 'Failed to save FAQ'
    });
  };

  const handleDelete = async (faqId) => {
    if (!confirm('Are you sure you want to delete this FAQ?')) return;
    
    toast.promise(adminAPI.deleteFAQ(selectedProduct, faqId), {
      loading: 'Deleting FAQ...',
      success: () => {
        loadFAQs();
        return 'FAQ deleted successfully!';
      },
      error: 'Failed to delete FAQ'
    });
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6 dark:text-gray-200">FAQ Management</h2>

      <div className="mb-6">
        <label className="block text-sm font-medium mb-2 dark:text-gray-300">Select Product</label>
        <select
          value={selectedProduct}
          onChange={(e) => setSelectedProduct(e.target.value)}
          className="w-full max-w-md px-4 py-2 border rounded-lg bg-white dark:bg-gray-800 dark:border-gray-600"
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
        {showForm ? 'Cancel' : 'Add FAQ'}
      </button>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg mb-6">
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2 dark:text-gray-300">Question</label>
            <input
              type="text"
              value={formData.question}
              onChange={(e) => setFormData({ ...formData, question: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg bg-white dark:bg-gray-800 dark:border-gray-600"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2 dark:text-gray-300">Answer</label>
            <textarea
              value={formData.answer}
              onChange={(e) => setFormData({ ...formData, answer: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg bg-white dark:bg-gray-800 dark:border-gray-600"
              rows="4"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2 dark:text-gray-300">Language</label>
            <select
              value={formData.language}
              onChange={(e) => setFormData({ ...formData, language: e.target.value })}
              className="w-full px-4 py-2 border rounded-lg bg-white dark:bg-gray-800 dark:border-gray-600"
            >
              <option value="en">English</option>
              <option value="hi">Hindi</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-lg">
              {editingFaq ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      )}
      
      {loading ? <SkeletonLoader /> : (
        <div className="space-y-4">
          {faqs.map(faq => (
            <div key={faq.id} className="border dark:border-gray-700 rounded-lg p-4">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold dark:text-gray-200">{faq.question}</h3>
                <button
                  onClick={() => handleDelete(faq.id)}
                  className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-gray-700 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <p className="text-gray-600 dark:text-gray-400 text-sm">{faq.answer}</p>
              <span className="inline-block mt-2 text-xs bg-gray-200 dark:bg-gray-600 px-2 py-1 rounded">
                {faq.language}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const UsersTab = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await adminAPI.listUsers();
      setUsers(response.data);
    } catch (error) {
      toast.error('Failed to load users.');
      console.error('Failed to load users:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    toast.promise(adminAPI.updateUserRole(userId, { role: newRole }), {
      loading: 'Updating role...',
      success: () => {
        loadUsers();
        return 'User role updated!';
      },
      error: (error) => `Failed to update role: ${error.response?.data?.detail || error.message}`
    });
  };

  if(loading) return <SkeletonLoader />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6 dark:text-gray-200">User Management</h2>

      <div className="space-y-3">
        {users.map(user => (
          <div key={user.id} className="border dark:border-gray-700 rounded-lg p-4 flex justify-between items-center">
            <div>
              <p className="font-medium dark:text-gray-200">{user.full_name || user.email}</p>
              <p className="text-sm text-gray-600 dark:text-gray-400">{user.email}</p>
              <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                Created: {new Date(user.created_at).toLocaleDateString()}
              </p>
            </div>
            <div>
              <select
                value={user.role}
                onChange={(e) => handleRoleChange(user.id, e.target.value)}
                className="px-3 py-1 border rounded-lg text-sm bg-white dark:bg-gray-800 dark:border-gray-600"
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, logsRes] = await Promise.all([
        adminAPI.getCacheStats(),
        adminAPI.getAuditLogs(50)
      ]);
      setStats(statsRes.data);
      setLogs(logsRes.data);
    } catch (error) {
      toast.error('Failed to load analytics data.');
      console.error('Failed to load analytics:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) return <SkeletonLoader />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6 dark:text-gray-200">Analytics & Audit Logs</h2>

      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-blue-50 dark:bg-blue-900/50 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <p className="text-sm text-blue-600 dark:text-blue-400 font-medium">Total Requests</p>
            <p className="text-3xl font-bold text-blue-900 dark:text-blue-200">{stats.total_requests}</p>
          </div>
          <div className="bg-green-50 dark:bg-green-900/50 border border-green-200 dark:border-green-800 rounded-lg p-4">
            <p className="text-sm text-green-600 dark:text-green-400 font-medium">Cache Hits</p>
            <p className="text-3xl font-bold text-green-900 dark:text-green-200">{stats.cache_hits}</p>
          </div>
          <div className="bg-yellow-50 dark:bg-yellow-900/50 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <p className="text-sm text-yellow-600 dark:text-yellow-400 font-medium">Hit Rate</p>
            <p className="text-3xl font-bold text-yellow-900 dark:text-yellow-200">{stats.hit_rate_percentage}%</p>
          </div>
          <div className="bg-purple-50 dark:bg-purple-900/50 border border-purple-200 dark:border-purple-800 rounded-lg p-4">
            <p className="text-sm text-purple-600 dark:text-purple-400 font-medium">Avg Response</p>
            <p className="text-3xl font-bold text-purple-900 dark:text-purple-200">{stats.average_response_time_sec}s</p>
          </div>
        </div>
      )}

      <h3 className="text-lg font-semibold mb-4 dark:text-gray-200">Recent Queries</h3>
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {logs.map(log => (
          <div key={log.id} className="border dark:border-gray-700 rounded-lg p-4">
            <p className="font-medium text-sm dark:text-gray-200">{log.question}</p>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 line-clamp-2">{log.answer}</p>
            <div className="flex gap-4 mt-2 text-xs text-gray-500 dark:text-gray-500">
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

    const promise = type === 'semantic' ? adminAPI.clearSemanticCache()
                  : type === 'redis' ? adminAPI.clearRedisCache()
                  : adminAPI.clearKnowledgeBase();

    toast.promise(promise, {
      loading: 'Clearing cache...',
      success: 'Cache cleared successfully!',
      error: (error) => `Failed to clear cache: ${error.response?.data?.detail || error.message}`
    });
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6 dark:text-gray-200">Cache & System Management</h2>

      <div className="space-y-4">
        <div className="border dark:border-gray-700 rounded-lg p-4">
          <h3 className="font-semibold mb-2 dark:text-gray-200">Semantic Cache (ChromaDB)</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Clear cached question-answer pairs from vector database.
          </p>
          <button
            onClick={() => handleClearCache('semantic')}
            className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700"
          >
            Clear Semantic Cache
          </button>
        </div>

        <div className="border dark:border-gray-700 rounded-lg p-4">
          <h3 className="font-semibold mb-2 dark:text-gray-200">Redis Cache</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Clear Redis cache including rate limits and temporary data.
          </p>
          <button
            onClick={() => handleClearCache('redis')}
            className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
          >
            Clear Redis Cache
          </button>
        </div>

        <div className="border border-red-300 dark:border-red-700 rounded-lg p-4 bg-red-50 dark:bg-red-900/30">
          <h3 className="font-semibold mb-2 text-red-800 dark:text-red-300">Knowledge Base</h3>
          <p className="text-sm text-red-700 dark:text-red-400 mb-4">
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
