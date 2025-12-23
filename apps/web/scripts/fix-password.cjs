const { Pool } = require('pg');

const pool = new Pool({ 
  connectionString: 'postgresql://user:password@localhost:5433/smartdvr' 
});

async function fixPassword() {
  try {
    // Get the hash from test@test.com account (the one that works)
    const testResult = await pool.query(`
      SELECT a.password 
      FROM account a 
      JOIN "user" u ON a."userId" = u.id 
      WHERE u.email = 'test@test.com'
    `);
    
    console.log('Working hash from test@test.com:', testResult.rows[0]?.password);
    
    // Get the user id for rugolop@gmail.com
    const userResult = await pool.query(`
      SELECT id FROM "user" WHERE email = 'rugolop@gmail.com'
    `);
    
    if (userResult.rows.length === 0) {
      console.log('User rugolop@gmail.com not found');
      return;
    }
    
    const userId = userResult.rows[0].id;
    console.log('User ID:', userId);
    
    // Update the password for rugolop@gmail.com with the same hash
    const workingHash = testResult.rows[0].password;
    
    await pool.query(`
      UPDATE account 
      SET password = $1 
      WHERE "userId" = $2
    `, [workingHash, userId]);
    
    console.log('Password updated for rugolop@gmail.com');
    console.log('You can now login with: Test1234');
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

fixPassword();
