Required sql table design due to execute python file: 

CREATE TABLE dbo.TableName (
    id NVARCHAR(100) PRIMARY KEY,  
    make NVARCHAR(100),                 
    name NVARCHAR(300),                 
    price FLOAT,            
    img_url NVARCHAR(MAX),              
    prd_url NVARCHAR(MAX),          
);
