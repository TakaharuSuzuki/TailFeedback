// ----- global -----
float FurLength = 0;
float UVScale   = 1.0f;
float Layer     = 0;
float3 vecLightDir = float4(0.8,0.8,1,0); 

// ----- transformations -----
float4x4 worldViewProj : WORLDVIEWPROJ;
float4x4 matWorld : WORLD;

// ----- texture -----
uniform sampler2D sampleFur : register(s0);
uniform sampler2D sampleNoise : register(s1);

// ----- structure -----
struct vertexInput
{
    float3 position                 : POSITION;
    float2 texCoordDiffuse          : TEXCOORD0;
    float3 normal                   : NORMAL;
	float3 tangent					: TANGENT;
};

struct vertexOutput 
{
    float4 HPOS     : POSITION;  
    float2 T0       : TEXCOORD0;
	float2 T1       : TEXCOORD1;
    float3 normal	: TEXCOORD2;
};

// ----- vertex shader -----
vertexOutput VS_TransformAndTexture(vertexInput IN)
{
    vertexOutput OUT = (vertexOutput)0; 
   
   float furOffset = (Layer-0.5)/50;
   
   float3 P = IN.position.xyz + (normalize(IN.normal) * FurLength * furOffset);
   
   float k =  pow(furOffset, 3);
   float3 outer = (0,0,0);
   if ( dot(cross(IN.normal, (0,0,-1)), IN.tangent) > 0 ){outer = cross(IN.normal, (0,0,-1) );}
   else{outer = -cross(IN.normal, (0,0,-1) );}
   
   P = P + outer*k;
   
   OUT.T0 = IN.texCoordDiffuse * UVScale;
   OUT.T1 = IN.texCoordDiffuse * UVScale*2;
   OUT.HPOS = mul(worldViewProj, float4(P, 1.0f));
   
   float3 normal = normalize(mul(matWorld, IN.normal));
   OUT.normal = normal;
   
   return OUT;
}

// ----- pixel shader -----
float4 PS_Textured( vertexOutput IN): COLOR
{
   float4 NoiseTexture = tex2D( sampleNoise,  IN.T1 );
   float furOffset = (Layer-0.5) / 50;
   if ( NoiseTexture.a <= 0.0 || NoiseTexture.r < furOffset)
   {
       discard;
   }
   
   float4 FurTexture = tex2D( sampleFur,  IN.T0 );
   float4 FinalColour = FurTexture; 
   
   float4 ambient = {0.9, 0.9, 0.9, 0.0};
   ambient = ambient * FinalColour;
   float4 diffuse = FinalColour;
   FinalColour = ambient + diffuse * dot(vecLightDir, IN.normal);
   
   FinalColour.a = FurTexture.a - furOffset;
   
   return FinalColour;       
}