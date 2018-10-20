procedure Test is
   type Point is record
      x : Integer;
      y : Integer;
   end record;

   p : Point;
   ptr : access Integer := p.x'Access;
begin
   ptr.all := 42;
end Ex1;
