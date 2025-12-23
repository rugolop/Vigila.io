const { Pool } = require('pg');
const bcrypt = require('bcryptjs');

const pool = new Pool({ 
  connectionString: 'postgresql://user:password@localhost:5433/smartdvr' 
});

async function resetPassword() {
  try {
    const hash = await bcrypt.hash('Test1234', 10);
    console.log('Generated hash:', hash);
    
    await pool.query('UPDATE account SET password = $1', [hash]);
    console.log('Password updated successfully!');
    
    // Verify
    const result = await pool.query('SELECT password FROM account');
    console.log('Stored hash:', result.rows[0].password);
    
    // Test comparison
    const match = await bcrypt.compare('Test1234', result.rows[0].password);
    console.log('Password verification:', match ? 'SUCCESS' : 'FAILED');
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

resetPassword();
