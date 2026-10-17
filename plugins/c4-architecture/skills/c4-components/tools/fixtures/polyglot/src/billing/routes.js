const router = require('express').Router();
router.post('/invoices', createInvoice);
router.get('/invoices/:id', getInvoice);
